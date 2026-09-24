"""Alumni profiling extras: card, notifications, perks, and editable contact details."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AacAppointmentSlot,
    Account,
    AlumniCard,
    AlumniNotification,
    AlumniPerk,
    AlumniPerkRedemption,
    AlumniSkill,
    EmailOutbox,
    Resume,
    SocCode,
    TracerSubmission,
)
from app.schemas import CardApplicationIn, ProfileUpdateIn
from app.services.email.dispatch import send_notice
from app.services.employment import resolve_current_employment
from app.services.jobs import ensure_job_timeline
from app.services.profile_completion import refresh_alumni_progress
from app.services.studies import serialize_studies
from app.services.validation import sanitize_alumni_path, sanitize_http_url

logger = logging.getLogger("careersense")


def _person_name(user: Account) -> str:
    profile = user.profile
    if profile:
        name = " ".join(part for part in [profile.first_name, profile.middle_name, profile.last_name] if part).strip()
        if name:
            return name
    return ""


def _mail_card(db: Session, user: Account, *, subject: str, headline: str, intro: str, detail: str = "") -> None:
    try:
        send_notice(
            db,
            kind="aac_status",
            to_address=user.personal_email,
            account_id=user.id,
            name=_person_name(user),
            subject=subject,
            headline=headline,
            intro=intro,
            detail=detail,
            path="/alumni/card",
            cta="Open your alumni card",
        )
        db.commit()
    except Exception:
        logger.exception("Alumni card email failed")
        db.rollback()


def maybe_send_gts_reminder(db: Session, user: Account) -> None:
    if user.status != "Active":
        return
    tracked = (
        db.query(EmailOutbox.id)
        .filter(EmailOutbox.account_id == user.id, EmailOutbox.kind == "gts_reminder")
        .first()
    )
    if tracked:
        return
    try:
        result = send_notice(
            db,
            kind="gts_reminder",
            to_address=user.personal_email,
            account_id=user.id,
            name=_person_name(user),
            subject="Graduate Tracer Survey reminder",
            headline="Graduate Tracer Survey reminder",
            intro=(
                "AAPS still needs your Graduate Tracer Survey. "
                "It is the official employment record used for alumni reports and your Angelenean Alumni Card."
            ),
            path="/alumni/resume",
            cta="Complete the Graduate Tracer Survey",
        )
        if result is not None and result.ok:
            db.add(
                EmailOutbox(
                    kind="gts_reminder",
                    account_id=user.id,
                    to_address=user.personal_email,
                    subject="Graduate Tracer Survey reminder",
                    status="sent",
                    sent_at=_now(),
                    text_body="",
                    html_body="",
                )
            )
        db.commit()
    except Exception:
        logger.exception("Graduate Tracer Survey reminder failed")
        db.rollback()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_submission(db: Session, account_id: int) -> TracerSubmission | None:
    return (
        db.query(TracerSubmission)
        .filter(TracerSubmission.account_id == account_id)
        .order_by(TracerSubmission.submitted_at.desc())
        .first()
    )


AAPS_OFFICE = {
    "name": "Alumni Affairs and Placement Services (AAPS)",
    "short_name": "AAPS",
    "location": "AUF Main Campus, MacArthur Highway, Angeles City",
    "hours": "Monday–Friday, 8:00 a.m. to 5:00 p.m.",
    "phone": "(+63-45) 625-2888 loc. 1788",
    "bring": "A valid government-issued ID that matches the name on your Angelenean Alumni Card.",
}
OAAPS_OFFICE = AAPS_OFFICE

MEMBERSHIP_TYPES = ["New", "Renewal", "Regular", "Lifetime", "Replacement"]
MEMBERSHIP_OPTIONS = [
    {"id": "New", "label": "New", "hint": "First-time Angelenean Alumni Card"},
    {"id": "Renewal", "label": "Renewal", "hint": "Card is expired or due for renewal"},
    {"id": "Regular", "label": "Regular", "hint": "Standard AAC membership"},
    {"id": "Lifetime", "label": "Lifetime", "hint": "Lifetime AAC membership"},
    {"id": "Replacement", "label": "Replacement", "hint": "Lost, damaged, or stolen card"},
]
CARD_STEPS = ["NotYetApplied", "ForVerification", "Approved", "ReadyForPickup", "Claimed"]
ISSUED_STATUSES = {"ReadyForPickup", "Claimed"}
APPLY_STATUSES = {"NotYetApplied", "ForRenewal"}
CARD_TRANSITIONS = {
    "ForVerification": ("Approved", "NotYetApplied"),
    "Approved": ("ReadyForPickup",),
    "ReadyForPickup": ("Claimed",),
    "Claimed": ("ForRenewal",),
    "ForRenewal": (),
    "NotYetApplied": (),
}
CARD_STATUS_MESSAGES = {
    "Approved": (
        "AAC application approved",
        "AAPS approved your Angelenean Alumni Card application. Your card is being prepared.",
    ),
    "ReadyForPickup": (
        "Alumni card ready for pickup",
        "Your Angelenean Alumni Card is ready. Claim it at AAPS, AUF Main Campus, during office hours.",
    ),
    "Claimed": (
        "Alumni card claimed",
        "Your Angelenean Alumni Card has been marked as claimed. Use it for AAPS services and partner perks.",
    ),
    "ForRenewal": (
        "Alumni card due for renewal",
        "Your Angelenean Alumni Card is due for renewal. Submit a renewal application to keep it current.",
    ),
    "NotYetApplied": (
        "AAC application returned",
        "AAPS returned your AAC application. Please review your information and apply again.",
    ),
}
CARD_META = {
    "NotYetApplied": {
        "label": "Not yet applied",
        "headline": "Apply for your Angelenean Alumni Card",
        "next": "Complete the AAC application so AAPS can verify your record.",
    },
    "ForVerification": {
        "label": "For verification",
        "headline": "AAPS is verifying your application",
        "next": "No further action now. You will be notified when it is approved.",
    },
    "Approved": {
        "label": "Approved",
        "headline": "Your application was approved",
        "next": "AAPS is preparing your card. Wait for the pickup notice.",
    },
    "ReadyForPickup": {
        "label": "Ready for pickup",
        "headline": "Your Angelenean Alumni Card is ready for pickup",
        "next": "Claim it at AAPS, AUF Main Campus, during office hours.",
    },
    "Claimed": {
        "label": "Claimed",
        "headline": "You have claimed your Angelenean Alumni Card",
        "next": "Use your card for AAPS services and partner perks.",
    },
    "ForRenewal": {
        "label": "For renewal",
        "headline": "Your alumni card is due for renewal",
        "next": "Submit a renewal application to keep your AAC current.",
    },
}
_STATUS_ALIASES = {
    "ActionNeeded": "NotYetApplied",
    "Pending": "NotYetApplied",
    "pending": "NotYetApplied",
    "Processing": "ForVerification",
    "Available": "ReadyForPickup",
    "Active": "Claimed",
}


def canonical_card_status(row: AlumniCard | None) -> str:
    if not row:
        return "NotYetApplied"
    status = (row.status or "").strip() or "Pending"
    if status in {"Pending", "pending"}:
        return "ForVerification" if row.submitted_at else "NotYetApplied"
    mapped = _STATUS_ALIASES.get(status, status)
    if mapped in CARD_META:
        return mapped
    return "NotYetApplied"


def serialize_card(row: AlumniCard | None) -> dict:
    status = canonical_card_status(row)
    meta = CARD_META[status]
    claimed = status == "Claimed"
    application = (row.application_json if row else None) or {}
    step_index = CARD_STEPS.index(status) if status in CARD_STEPS else 0
    return {
        "status": status,
        "label": meta["label"],
        "headline": meta["headline"],
        "next_action": meta["next"],
        "card_number": (row.card_number or "") if row and claimed else "",
        "issued_at": row.issued_at if row else None,
        "expires_at": row.expires_at.isoformat() if row and row.expires_at else None,
        "submitted_at": row.submitted_at if row else None,
        "pickup_ready_at": row.pickup_ready_at if row else None,
        "pickup_location": (row.pickup_location if row and row.pickup_location else AAPS_OFFICE["location"]),
        "can_view": claimed,
        "can_apply": status in APPLY_STATUSES,
        "needs_action": status in APPLY_STATUSES,
        "show_pickup": status == "ReadyForPickup",
        "step_index": step_index,
        "membership_type": application.get("membership_type") or "",
        "application": {
            "phone": application.get("phone") or "",
            "city": application.get("city") or "",
            "country_residence": application.get("country_residence") or "",
            "mailing_address": application.get("mailing_address") or "",
            "company_affiliation": application.get("company_affiliation") or "",
            "position": application.get("position") or "",
            "membership_type": application.get("membership_type") or "",
            "birthday": application.get("birthday") or "",
            "appointment_date": application.get("appointment_date") or "",
            "appointment_time": application.get("appointment_time") or "",
            "college": application.get("college") or "",
            "course": application.get("course") or "",
        }
        if application
        else None,
    }


def ensure_card(db: Session, user: Account) -> AlumniCard:
    row = user.alumni_card
    if row:
        return row
    row = AlumniCard(account_id=user.id, status="NotYetApplied", pickup_location=AAPS_OFFICE["location"])
    db.add(row)
    db.flush()
    return row


def serialize_notification(row: AlumniNotification) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "body": row.body,
        "category": row.category,
        "link": sanitize_alumni_path(row.link or ""),
        "created_at": row.created_at,
        "read": row.read_at is not None,
    }


def list_notifications(db: Session, user: Account) -> list[dict]:
    rows = (
        db.query(AlumniNotification)
        .filter(AlumniNotification.account_id == user.id)
        .order_by(AlumniNotification.created_at.desc())
        .limit(20)
        .all()
    )
    return [serialize_notification(row) for row in rows]


def mark_notification_read(db: Session, user: Account, notification_id: int) -> list[dict]:
    row = db.get(AlumniNotification, notification_id)
    if not row or row.account_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if row.read_at is None:
        row.read_at = _now()
        from app.services.profile_updates import mark_request_viewed

        mark_request_viewed(db, row.id, user.id)
        db.commit()
    return list_notifications(db, user)


def mark_all_notifications_read(db: Session, user: Account) -> list[dict]:
    unread = (
        db.query(AlumniNotification)
        .filter(AlumniNotification.account_id == user.id, AlumniNotification.read_at.is_(None))
        .all()
    )
    now = _now()
    for row in unread:
        row.read_at = now
    db.commit()
    return list_notifications(db, user)


def _perk_status(perk: AlumniPerk, card_status: str, redeemed: AlumniPerkRedemption | None) -> str:
    today = date.today()
    if redeemed:
        return "Used"
    if perk.valid_to and perk.valid_to < today:
        return "Expired"
    if perk.requires_active_card and card_status not in ISSUED_STATUSES:
        return "Locked"
    if perk.valid_from and perk.valid_from > today:
        return "Locked"
    return "Available"


def serialize_perk(perk: AlumniPerk, card_status: str, redeemed: AlumniPerkRedemption | None) -> dict:
    status = _perk_status(perk, card_status, redeemed)
    return {
        "id": perk.id,
        "name": perk.name,
        "partner": (perk.partner or perk.name),
        "description": perk.description,
        "discount": perk.discount,
        "how_to_claim": perk.how_to_claim,
        "terms": perk.how_to_claim,
        "eligibility": perk.eligibility or "",
        "category": perk.category or "",
        "contact": perk.contact or "",
        "website": sanitize_http_url(perk.website or ""),
        "has_image": bool(perk.image_path),
        "image_url": f"/api/alumni/perks/{perk.id}/image" if perk.image_path else None,
        "valid_from": perk.valid_from.isoformat() if perk.valid_from else None,
        "valid_to": perk.valid_to.isoformat() if perk.valid_to else None,
        "status": status,
        "code": redeemed.code if redeemed else "",
        "requires_card": bool(perk.requires_active_card),
    }


def list_perks(db: Session, user: Account) -> list[dict]:
    card = ensure_card(db, user)
    perks = db.query(AlumniPerk).filter(AlumniPerk.active.is_(True)).order_by(AlumniPerk.id.asc()).all()
    redemptions = {
        row.perk_id: row
        for row in db.query(AlumniPerkRedemption).filter(AlumniPerkRedemption.account_id == user.id).all()
    }
    return [serialize_perk(perk, canonical_card_status(card), redemptions.get(perk.id)) for perk in perks]


def claim_perk(db: Session, user: Account, perk_id: int) -> list[dict]:
    perk = db.get(AlumniPerk, perk_id)
    if not perk or not perk.active:
        raise HTTPException(status_code=404, detail="Benefit not found.")
    card = ensure_card(db, user)
    existing = (
        db.query(AlumniPerkRedemption)
        .filter(AlumniPerkRedemption.account_id == user.id, AlumniPerkRedemption.perk_id == perk.id)
        .first()
    )
    status = _perk_status(perk, canonical_card_status(card), existing)
    if status == "Used":
        return list_perks(db, user)
    if status == "Expired":
        raise HTTPException(status_code=400, detail="This benefit has expired.")
    if status == "Locked":
        raise HTTPException(status_code=400, detail="This benefit is locked until your alumni card is ready.")
    db.add(
        AlumniPerkRedemption(
            account_id=user.id,
            perk_id=perk.id,
            code=f"AUF-{perk.id:02d}-{uuid4().hex[:6].upper()}",
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return list_perks(db, user)


def update_contact_profile(db: Session, user: Account, payload: ProfileUpdateIn) -> None:
    profile = user.profile
    if profile is None:
        raise HTTPException(status_code=400, detail="No alumni profile is on file.")
    profile.country_residence = (payload.country_residence or "").strip() or "Philippines"
    profile.phone = (payload.phone or "").strip()
    profile.city = (payload.city or "").strip()
    profile.address = (payload.address or "").strip()
    profile.husband_surname = (payload.husband_surname or "").strip()
    profile.bio = (payload.bio or "").strip()
    db.commit()


def set_alumni_card_status(
    db: Session,
    user: Account,
    status: str,
    *,
    notify: bool = False,
    pickup_location: str = "",
    card_number: str = "",
) -> AlumniCard:
    """Internal status write. Alumni cannot call this; OAAPS uses transition_alumni_card_status."""
    card = ensure_card(db, user)
    card.status = status
    if status == "ReadyForPickup":
        card.pickup_ready_at = card.pickup_ready_at or _now()
        if pickup_location.strip():
            card.pickup_location = pickup_location.strip()[:200]
    if status == "Claimed":
        card.issued_at = card.issued_at or _now()
        card.card_number = (card_number.strip() or card.card_number or f"AUF-{user.id:04d}")[:40]
    if status == "NotYetApplied":
        card.submitted_at = None
    db.commit()
    refresh_alumni_progress(db, user, notify=notify)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return card


def _notify_card_status(db: Session, user: Account, status: str, note: str = "") -> None:
    title_body = CARD_STATUS_MESSAGES.get(status)
    if not title_body:
        return
    title, body = title_body
    if note.strip():
        body = f"{body} {note.strip()}".strip()
    db.add(
        AlumniNotification(
            account_id=user.id,
            title=title,
            body=body[:1000],
            category="card",
            link="/alumni/card",
        )
    )


def transition_alumni_card_status(
    db: Session,
    user: Account,
    status: str,
    *,
    pickup_location: str = "",
    card_number: str = "",
    note: str = "",
) -> tuple[AlumniCard, bool]:
    card = ensure_card(db, user)
    current = canonical_card_status(card)
    target = (status or "").strip()
    if target not in CARD_META:
        raise HTTPException(status_code=400, detail="Unsupported alumni card status.")
    if current == target:
        return card, True
    allowed = CARD_TRANSITIONS.get(current, ())
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change the alumni card from {CARD_META[current]['label']} to {CARD_META[target]['label']}.",
        )
    _notify_card_status(db, user, target, note)
    card = set_alumni_card_status(
        db,
        user,
        target,
        notify=True,
        pickup_location=pickup_location,
        card_number=card_number,
    )
    return card, False


ACTIVE_CARD_STATUSES = {"ForVerification", "Approved", "ReadyForPickup", "Claimed", "ForRenewal"}


def _clean(value) -> str:
    return str(value or "").strip()


def _latest_resume(db: Session, account_id: int) -> Resume | None:
    return (
        db.query(Resume)
        .filter(Resume.account_id == account_id)
        .order_by(Resume.created_at.desc())
        .first()
    )


def gts_is_submitted(db: Session, user: Account) -> bool:
    return _latest_submission(db, user.id) is not None


def _first_filled(*values: str) -> tuple[str, str]:
    for origin, value in values:
        text = _clean(value)
        if text:
            return text, origin
    return "", ""


def _resume_career(parsed: dict) -> tuple[str, str]:
    if not isinstance(parsed, dict):
        return "", ""
    experiences = parsed.get("experiences") if isinstance(parsed.get("experiences"), list) else []
    current = next(
        (job for job in experiences if isinstance(job, dict) and str(job.get("is_current") or "").lower() == "yes"),
        None,
    )
    job = current or (experiences[0] if experiences and isinstance(experiences[0], dict) else {})
    return _clean(job.get("employer")), _clean(job.get("job_title"))


def _aac_field(key: str, label: str, value: str, *, locked: bool, required: bool, origin: str) -> dict:
    text = _clean(value)
    return {
        "key": key,
        "label": label,
        "value": text,
        "locked": bool(locked and text),
        "required": required,
        "origin": origin if text else "",
        "status": "filled" if text else ("needed" if required else "optional"),
    }


def build_aac_prefill(db: Session, user: Account) -> list[dict]:
    """Registry and account identity win. GTS fills contact. Resume is career-only."""
    profile = user.profile
    record = user.university_record
    submission = _latest_submission(db, user.id)
    gts = (submission.data_json if submission and isinstance(submission.data_json, dict) else {}) or {}
    resume = _latest_resume(db, user.id)
    parsed = (resume.parsed_json if resume and isinstance(resume.parsed_json, dict) else {}) or {}
    resume_employer, resume_title = _resume_career(parsed)

    first, first_origin = _first_filled(
        ("registry", record.first_name if record else ""),
        ("account", profile.first_name if profile else ""),
        ("gts", gts.get("first_name")),
    )
    middle, middle_origin = _first_filled(
        ("registry", record.middle_name if record else ""),
        ("account", profile.middle_name if profile else ""),
        ("gts", gts.get("middle_name")),
    )
    last, last_origin = _first_filled(
        ("registry", record.last_name if record else ""),
        ("account", profile.last_name if profile else ""),
        ("gts", gts.get("last_name")),
    )
    year, year_origin = _first_filled(
        ("registry", record.year_graduated if record else ""),
        ("account", profile.year_graduated if profile else ""),
        ("gts", gts.get("year_graduated")),
    )
    course, course_origin = _first_filled(
        ("registry", record.degree if record else ""),
        ("account", profile.degree if profile else ""),
        ("gts", gts.get("degree")),
    )
    college, college_origin = _first_filled(("registry", record.college if record else ""),)
    birthday, birthday_origin = _first_filled(
        ("account", profile.birth_date.isoformat() if profile and profile.birth_date else ""),
        ("gts", gts.get("birthday") or gts.get("date_of_birth") or gts.get("birth_date")),
    )
    phone, phone_origin = _first_filled(
        ("account", profile.phone if profile else ""),
        ("gts", gts.get("phone") or gts.get("mobile") or gts.get("mobile_number") or gts.get("contact_number")),
    )
    address, address_origin = _first_filled(
        ("account", profile.address if profile else ""),
        ("gts", gts.get("home_address") or gts.get("address") or gts.get("mailing_address")),
    )
    email = _clean(user.personal_email)
    gts_email = _clean(gts.get("personal_email") or gts.get("email"))
    employed = _clean(gts.get("is_currently_employed")).lower()
    if employed == "no":
        employer, employer_origin = "", ""
        position, position_origin = "", ""
    else:
        employer, employer_origin = _first_filled(
            ("gts", gts.get("pres_emp") or gts.get("current_employer")),
            ("resume", resume_employer),
        )
        position, position_origin = _first_filled(
            ("gts", gts.get("pres_occ") or gts.get("current_occupation")),
            ("resume", resume_title),
        )
    fields = [
        _aac_field("email", "Email", email, locked=True, required=True, origin="account" if email else ""),
        _aac_field("last_name", "Last name", last, locked=last_origin == "registry", required=True, origin=last_origin),
        _aac_field("first_name", "First name", first, locked=first_origin == "registry", required=True, origin=first_origin),
        _aac_field("middle_name", "Middle name", middle, locked=middle_origin == "registry", required=False, origin=middle_origin),
        _aac_field("student_id", "Student ID number", user.linked_student_id or "", locked=True, required=True, origin="registry"),
        _aac_field("birthday", "Date of birth", birthday, locked=False, required=True, origin=birthday_origin),
        _aac_field("year_graduated", "Year of graduation", year, locked=year_origin == "registry", required=True, origin=year_origin),
        _aac_field("college", "College", college, locked=college_origin == "registry", required=True, origin=college_origin),
        _aac_field("course", "Course or program", course, locked=course_origin == "registry", required=True, origin=course_origin),
        _aac_field("phone", "Mobile number", phone, locked=False, required=True, origin=phone_origin),
        _aac_field("home_address", "Home address", address, locked=False, required=True, origin=address_origin),
    ]
    if gts_email and gts_email.lower() != email.lower():
        fields.insert(1, _aac_field("personal_email", "Personal email address", gts_email, locked=False, required=False, origin="gts"))
    if employer or position:
        fields.append(_aac_field("company_affiliation", "Employer", employer, locked=False, required=False, origin=employer_origin))
        fields.append(_aac_field("position", "Occupation", position, locked=False, required=False, origin=position_origin))
    return fields


def _booked_count(db: Session, slot_date: date, slot_time: str) -> int:
    day = slot_date.isoformat()
    rows = (
        db.query(AlumniCard)
        .filter(AlumniCard.status.in_(ACTIVE_CARD_STATUSES))
        .all()
    )
    count = 0
    for row in rows:
        application = row.application_json or {}
        if application.get("appointment_date") == day and application.get("appointment_time") == slot_time:
            count += 1
    return count


def available_aac_slots(db: Session, today: date | None = None) -> list[dict]:
    today = today or date.today()
    rows = (
        db.query(AacAppointmentSlot)
        .filter(AacAppointmentSlot.active.is_(True), AacAppointmentSlot.slot_date >= today)
        .order_by(AacAppointmentSlot.slot_date, AacAppointmentSlot.slot_time)
        .all()
    )
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        remaining = max(0, int(row.capacity or 0) - _booked_count(db, row.slot_date, row.slot_time))
        if remaining <= 0:
            continue
        grouped.setdefault(row.slot_date.isoformat(), []).append({"time": row.slot_time, "remaining": remaining})
    return [{"date": day, "times": times} for day, times in grouped.items()]


def reserve_aac_slot(db: Session, slot_date: date, slot_time: str) -> None:
    slot = (
        db.query(AacAppointmentSlot)
        .filter(
            AacAppointmentSlot.slot_date == slot_date,
            AacAppointmentSlot.slot_time == slot_time,
            AacAppointmentSlot.active.is_(True),
        )
        .first()
    )
    if slot is None or slot.slot_date < date.today():
        raise HTTPException(status_code=400, detail="That appointment is no longer available. Choose another time.")
    if _booked_count(db, slot.slot_date, slot.slot_time) >= int(slot.capacity or 0):
        raise HTTPException(status_code=400, detail="That appointment is fully booked. Choose another time.")


def card_for_alumni(db: Session, user: Account, card: AlumniCard | None) -> dict:
    payload = serialize_card(card)
    submitted = gts_is_submitted(db, user)
    payload["gts_completed"] = submitted
    if payload["status"] in APPLY_STATUSES and not submitted:
        payload["can_apply"] = False
        payload["needs_action"] = False
        payload["headline"] = "Submit the Graduate Tracer Survey to get your alumni card"
        payload["next_action"] = "The Angelenean Alumni Card is available after you submit the GTS. Employment status is not required."
    return payload


def apply_card_application(db: Session, user: Account, payload: CardApplicationIn) -> dict:
    if not gts_is_submitted(db, user):
        raise HTTPException(status_code=400, detail="Submit the Graduate Tracer Survey before applying for an alumni card.")
    if not payload.pickup_acknowledged:
        raise HTTPException(status_code=400, detail="Confirm that you will attend the selected AAC appointment.")
    reserve_aac_slot(db, payload.appointment_date, payload.appointment_time)
    card = ensure_card(db, user)
    status = canonical_card_status(card)
    if status not in APPLY_STATUSES:
        raise HTTPException(status_code=400, detail="An Angelenean Alumni Card application is already on file.")
    profile = user.profile
    record = user.university_record
    phone = payload.phone.strip()
    city = payload.city.strip() or (profile.city if profile else "")
    country = (payload.country_residence or "").strip() or (profile.country_residence if profile else "") or "Philippines"
    address = payload.mailing_address.strip()
    birthday = payload.birthday.isoformat()
    membership = payload.membership_type
    if status == "ForRenewal" and membership == "New":
        membership = "Renewal"
    card.application_json = {
        "phone": phone,
        "city": city,
        "country_residence": country,
        "mailing_address": address,
        "company_affiliation": payload.company_affiliation.strip(),
        "position": payload.position.strip(),
        "membership_type": membership,
        "birthday": birthday,
        "student_number": user.linked_student_id or "",
        "email": user.personal_email,
        "first_name": (record.first_name if record else "") or (profile.first_name if profile else ""),
        "middle_name": (record.middle_name if record else "") or (profile.middle_name if profile else ""),
        "last_name": (record.last_name if record else "") or (profile.last_name if profile else ""),
        "year_graduated": (record.year_graduated if record else "") or (profile.year_graduated if profile else ""),
        "college": record.college if record else "",
        "course": (record.degree if record else "") or (profile.degree if profile else ""),
        "appointment_date": payload.appointment_date.isoformat(),
        "appointment_time": payload.appointment_time,
        "pickup_acknowledged": True,
    }
    card.submitted_at = _now()
    card.status = "ForVerification"
    card.pickup_location = AAPS_OFFICE["location"]
    if profile is not None:
        profile.phone = phone
        if address:
            profile.address = address
        if city:
            profile.city = city
        if country:
            profile.country_residence = country
        profile.birth_date = payload.birthday
    db.add(
        AlumniNotification(
            account_id=user.id,
            title="Angelenean Alumni Card application received",
            body=(
                "AAPS is verifying your AAC application. "
                f"Your appointment is {payload.appointment_date.isoformat()} at {payload.appointment_time}."
            ),
            category="card",
        )
    )
    db.commit()
    db.refresh(card)
    _mail_card(
        db,
        user,
        subject="Alumni card application received",
        headline="Alumni card application received",
        intro="AAPS received your Angelenean Alumni Card application and will verify your record.",
        detail=f"Appointment: {payload.appointment_date.isoformat()} at {payload.appointment_time}.",
    )
    refresh_alumni_progress(db, user, notify=True)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return card_workspace(db, user)


def card_workspace(db: Session, user: Account) -> dict:
    profile = user.profile
    card = ensure_card(db, user)
    jobs = ensure_job_timeline(db, user)
    current = next((job for job in jobs if job.get("is_current")), jobs[0] if jobs else None)
    db.commit()
    refresh_alumni_progress(db, user, notify=False)
    try:
        db.commit()
    except Exception:
        db.rollback()
    birthday = ""
    if profile and profile.birth_date:
        birthday = profile.birth_date.isoformat()
    elif card.application_json:
        birthday = (card.application_json or {}).get("birthday") or ""
    return {
        "card": card_for_alumni(db, user, card),
        "office": AAPS_OFFICE,
        "membership_types": MEMBERSHIP_TYPES,
        "membership_options": MEMBERSHIP_OPTIONS,
        "prefill": build_aac_prefill(db, user),
        "appointments": available_aac_slots(db),
        "identity": {
            "first_name": profile.first_name if profile else "",
            "middle_name": profile.middle_name if profile else "",
            "last_name": profile.last_name if profile else "",
            "degree": profile.degree if profile else "",
            "year_graduated": profile.year_graduated if profile else "",
            "has_photo": bool(profile and profile.photo_path),
            "student_id": user.linked_student_id or "",
            "student_number": user.linked_student_id or "",
            "birthday": birthday,
            "email": user.personal_email,
        },
        "contact": {
            "phone": profile.phone if profile else "",
            "city": profile.city if profile else "",
            "country_residence": profile.country_residence if profile else "Philippines",
            "email": user.personal_email,
            "company_affiliation": (current or {}).get("company") or "",
            "position": (current or {}).get("job_title") or "",
        },
        "steps": [
            {"id": "NotYetApplied", "label": "Not yet applied"},
            {"id": "ForVerification", "label": "For verification"},
            {"id": "Approved", "label": "Approved"},
            {"id": "ReadyForPickup", "label": "Ready for pickup"},
            {"id": "Claimed", "label": "Claimed"},
        ],
    }


def ensure_starter_notifications(db: Session, user: Account, card: AlumniCard, has_tracer: bool) -> None:
    if db.query(AlumniNotification).filter(AlumniNotification.account_id == user.id).count():
        return
    items = []
    status = canonical_card_status(card)
    if status == "Claimed":
        items.append(
            (
                "Angelenean Alumni Card claimed",
                "Your AAC is on file. Open Alumni card if you need pickup history or your digital ID.",
                "card",
            )
        )
    elif status == "ReadyForPickup":
        items.append(
            (
                "Angelenean Alumni Card ready for pickup",
                "Claim your card at AAPS, AUF Main Campus, during office hours. Bring a valid ID.",
                "card",
            )
        )
    elif status == "Approved":
        items.append(
            (
                "AAC application approved",
                "AAPS approved your application and is preparing your Angelenean Alumni Card.",
                "card",
            )
        )
    elif status == "ForVerification":
        items.append(
            (
                "AAC application is for verification",
                "AAPS is verifying your Angelenean Alumni Card application.",
                "card",
            )
        )
    elif status == "ForRenewal":
        items.append(
            (
                "Alumni card due for renewal",
                "Submit a renewal application on Alumni card to keep your AAC current.",
                "card",
            )
        )
    else:
        items.append(
            (
                "Apply for your Angelenean Alumni Card",
                "Complete the AAC application so AAPS can verify your record and prepare your card.",
                "card",
            )
        )
    items.append(
        (
            "Partner cafe discount",
            "A 15% alumni discount at selected Angeles cafes is now in Perks & discounts.",
            "perk",
        )
    )
    items.append(
        (
            "AAPS announcement",
            "Keep your profile current so AAPS can reach you about homecoming and placement activities.",
            "announcement",
        )
    )
    if not has_tracer:
        items.append(
            (
                "Complete your Graduate Tracer Survey",
                "AAPS uses the tracer as your official employment record. You can enter answers on Resume & tracer.",
                "tracer",
            )
        )
    for title, body, category in items:
        db.add(
            AlumniNotification(
                account_id=user.id,
                title=title,
                body=body,
                category=category,
            )
        )
    db.flush()


def assemble_profile(db: Session, user: Account, *, notify_badges: bool = False) -> dict:
    latest = _latest_submission(db, user.id)
    data = latest.data_json if latest else {}
    profile = user.profile
    record = user.university_record
    alignment = user.alignment
    jobs = ensure_job_timeline(db, user)
    card = ensure_card(db, user)
    ensure_starter_notifications(db, user, card, latest is not None)
    if latest is None:
        maybe_send_gts_reminder(db, user)
    db.commit()
    completion = refresh_alumni_progress(db, user, notify=notify_badges)

    skills = [s.skill_name for s in db.query(AlumniSkill).filter(AlumniSkill.account_id == user.id).all()]
    if not skills:
        skills = [str(item).strip() for item in (data.get("skills") or []) if str(item).strip()]
    studies = serialize_studies(db, user.id)
    soc = db.get(SocCode, latest.soc_code) if latest and latest.soc_code else None
    current_job = next((job for job in jobs if job.get("is_current")), None)
    notifications = list_notifications(db, user)
    alignment_status = (
        alignment.alignment_justification
        if alignment
        else (latest.alignment_status if latest else "Unknown")
    )
    employment = resolve_current_employment(data)
    related = ""
    if employment.currently_employed:
        related = data.get("first_related") if employment.present_is_first else data.get("present_related_degree") or ""

    return {
        "user": {
            "id": user.id,
            "email": user.personal_email,
            "status": user.status,
            "student_id": user.linked_student_id,
        },
        "profile": {
            "first_name": profile.first_name if profile else "",
            "middle_name": profile.middle_name if profile else "",
            "last_name": profile.last_name if profile else "",
            "husband_surname": profile.husband_surname if profile else "",
            "country_residence": profile.country_residence if profile else "Philippines",
            "degree": profile.degree if profile else (record.degree if record else ""),
            "year_graduated": profile.year_graduated if profile else (record.year_graduated if record else ""),
            "phone": (profile.phone if profile else "") or "",
            "city": (profile.city if profile else "") or "",
            "address": (profile.address if profile else "") or "",
            "bio": (profile.bio if profile else "") or "",
            "has_photo": bool(profile and profile.photo_path),
            "has_cover": bool(profile and profile.cover_path),
            "college": record.college if record else "",
            "course_code": record.course_code if record else "",
        },
        "skills": skills,
        "further_studies": studies,
        "jobs": jobs,
        "card": card_for_alumni(db, user, card),
        "perks": list_perks(db, user),
        "notifications": notifications,
        "unread_count": sum(1 for item in notifications if not item["read"]),
        "career": {
            "alignment_status": alignment_status,
            "alignment_detail": alignment.justification_detail if alignment else "",
            "field": (soc.category if soc and soc.category else "") or (current_job.get("industry") if current_job else ""),
            "related_to_degree": related,
            "employment_status": data.get("is_currently_employed") or ("Yes" if current_job else ""),
            "time_to_first_job": data.get("time_to_first_job") or "",
        },
        "latest_submission": {
            "id": latest.id,
            "submitted_at": latest.submitted_at,
            "alignment_status": latest.alignment_status,
            "job_title": employment.occupation or data.get("current_occupation"),
            "employer": employment.employer or data.get("current_employer"),
            "data": data,
        }
        if latest
        else None,
        "completion": completion,
    }

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified

from app.db import get_db
from app.deps import require_admin
from app.models import Account, AdminLog, AlumniCard, AlumniProfile, UniversityRecord
from app.schemas import AppointmentSlotIn, CardStatusIn
from app.services.alumni_hub import (
    CARD_META,
    CARD_TRANSITIONS,
    canonical_card_status,
    serialize_card,
    transition_alumni_card_status,
)
from app.services.card_renewal import MANILA, RENEWAL_BATCH_YEAR, assess_card_renewal
from app.services.email.dispatch import send_notice

router = APIRouter(prefix="/api/admin/cards", tags=["admin-cards"])
logger = logging.getLogger("careersense")


def _log(db: Session, admin_id: int, action: str, target_id, old=None, new=None) -> None:
    db.add(
        AdminLog(
            admin_id=admin_id,
            action_type=action,
            target_id=str(target_id or ""),
            old_value=old,
            new_value=new,
        )
    )


def _account_name(account: Account) -> str:
    if account.profile:
        parts = [account.profile.first_name, account.profile.middle_name, account.profile.last_name]
        name = " ".join(part for part in parts if part).strip()
        if name:
            return name
    return account.personal_email


REQUESTING_STATUS = "ForVerification"
PRINTING_STATUS = "Approved"
PRINTED_STATUS = "ReadyForPickup"
CLAIMED_STATUS = "Claimed"
FOR_RENEWAL_STATUS = "ForRenewal"
# Manual placement steps. For Renewal is not one of them; the next renewal date decides it.
OFFICE_STEPS = (CLAIMED_STATUS, REQUESTING_STATUS, PRINTING_STATUS, PRINTED_STATUS)


def _blank(value) -> str:
    return str(value or "").strip()


def _application(account: Account) -> dict:
    card = account.alumni_card
    raw = card.application_json if card else None
    return raw if isinstance(raw, dict) else {}


def _academic(account: Account) -> dict:
    application = _application(account)
    record = account.university_record
    profile = account.profile
    college = _blank(record.college if record else "") or _blank(application.get("college"))
    course = _blank(record.degree if record else "") or _blank(application.get("course")) or _blank(profile.degree if profile else "")
    year = (
        _blank(record.year_graduated if record else "")
        or _blank(profile.year_graduated if profile else "")
        or _blank(application.get("year_graduated"))
    )
    return {"college": college, "course": course, "year_graduated": year}


def _registry_linked(account: Account) -> bool:
    return bool((account.linked_student_id or "").strip()) and account.university_record is not None


def _assessment(account: Account, year, issued_at) -> dict:
    return assess_card_renewal(year, issued_at, linked=_registry_linked(account))


def _office_status(application: dict) -> str:
    return str((application or {}).get("office_status") or "").strip()


def _status_unknown(id_status: str, application: dict) -> bool:
    """Previous batches stay Undefined until the office records a card step."""
    return id_status != "Defined" and not _office_status(application)


def _renewal_due(renewal: dict) -> bool:
    raw = (renewal or {}).get("next_renewal_on")
    if not raw:
        return False
    try:
        due_on = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return False
    return due_on <= datetime.now(MANILA).date()


def _display_status(status: str, id_status: str, application: dict, renewal: dict) -> str:
    if _status_unknown(id_status, application):
        return "Undefined"
    if status in {CLAIMED_STATUS, FOR_RENEWAL_STATUS}:
        return FOR_RENEWAL_STATUS if _renewal_due(renewal) else CLAIMED_STATUS
    return status


def _renewal_actions(status: str, application: dict, id_status: str, renewal: dict) -> list[str]:
    """Manual card steps. For Renewal follows the next renewal date."""
    membership = str((application or {}).get("membership_type") or "")
    shown = _display_status(status, id_status, application, renewal)
    if shown == "Undefined" and membership == "Renewal":
        return list(OFFICE_STEPS)
    if shown == "ForVerification" and membership == "Renewal":
        return ["Approved"]
    if shown == "Approved":
        return ["ReadyForPickup"]
    if shown == "ReadyForPickup":
        return ["Claimed"]
    if shown == "ForRenewal":
        return ["ForVerification"]
    return []


def _remember_office_status(card: AlumniCard, status: str) -> None:
    application = dict(card.application_json or {})
    if str(application.get("membership_type") or "") != "Renewal":
        return
    application["office_status"] = status
    card.application_json = application
    flag_modified(card, "application_json")


def _stamp(value) -> str | None:
    if value is None or value == "":
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _renewal_clause():
    membership = AlumniCard.application_json["membership_type"].as_string()
    return or_(AlumniCard.status == "ForRenewal", membership == "Renewal")


def _college_expr():
    stored = AlumniCard.application_json["college"].as_string()
    return func.coalesce(func.nullif(UniversityRecord.college, ""), func.nullif(stored, ""), "")


def _year_expr():
    stored = AlumniCard.application_json["year_graduated"].as_string()
    return func.coalesce(
        func.nullif(UniversityRecord.year_graduated, ""),
        func.nullif(AlumniProfile.year_graduated, ""),
        func.nullif(stored, ""),
        "",
    )


def _defined_batch_clause():
    year = _year_expr()
    return and_(func.length(year) == 4, year.op("GLOB")("[0-9][0-9][0-9][0-9]"), year >= str(RENEWAL_BATCH_YEAR))


def _office_confirmed_clause():
    recorded = AlumniCard.application_json["office_status"].as_string()
    return func.length(func.trim(func.coalesce(recorded, ""))) > 0


def _unknown_card_clause():
    return and_(~_defined_batch_clause(), ~_office_confirmed_clause())


def _shown_for(account: Account) -> str:
    card = serialize_card(account.alumni_card)
    academic = _academic(account)
    renewal = _assessment(account, academic["year_graduated"], card.get("issued_at"))
    return _display_status(card["status"], renewal["id_status"], _application(account), renewal)


def _resting_counts(summary_query) -> tuple[int, int]:
    rows = summary_query.filter(
        ~_unknown_card_clause(),
        AlumniCard.status.in_((CLAIMED_STATUS, FOR_RENEWAL_STATUS)),
    ).all()
    claimed = 0
    renewal = 0
    for account in rows:
        shown = _shown_for(account)
        if shown == FOR_RENEWAL_STATUS:
            renewal += 1
        elif shown == CLAIMED_STATUS:
            claimed += 1
    return claimed, renewal


def _serialize_item(account: Account) -> dict:
    card = serialize_card(account.alumni_card)
    application = _application(account)
    academic = _academic(account)
    status = card["status"]
    claimed = status == "Claimed"
    renewal = _assessment(account, academic["year_graduated"], card.get("issued_at"))
    return {
        "id": account.id,
        "email": account.personal_email,
        "name": _account_name(account),
        "student_id": account.linked_student_id,
        "degree": academic["course"],
        "college": academic["college"],
        "course": academic["course"],
        "year_graduated": academic["year_graduated"],
        "status": status,
        "display_status": _display_status(status, renewal["id_status"], application, renewal),
        "label": card["label"],
        "submitted_at": card.get("submitted_at"),
        "printed_at": card.get("pickup_ready_at"),
        "claimed_at": card.get("issued_at") if claimed else None,
        "expires_at": card.get("expires_at"),
        "id_status": renewal["id_status"],
        "id_note": renewal["id_note"],
        "eligibility": renewal["eligibility"],
        "eligibility_label": renewal["eligibility_label"],
        "next_renewal_on": renewal["next_renewal_on"],
        "eligibility_note": renewal["note"],
        "membership_type": application.get("membership_type") or card.get("membership_type") or "",
        "card_number": card.get("card_number") or "",
        "claiming_date": renewal["claiming_date"],
        "actions": _renewal_actions(status, application, renewal["id_status"], renewal),
        "next_statuses": list(CARD_TRANSITIONS.get(status, ())),
    }


def _card_query(db: Session):
    return (
        db.query(Account)
        .join(AlumniCard, AlumniCard.account_id == Account.id)
        .outerjoin(AlumniProfile, AlumniProfile.account_id == Account.id)
        .outerjoin(UniversityRecord, UniversityRecord.student_id == Account.linked_student_id)
        .options(
            joinedload(Account.profile),
            joinedload(Account.alumni_card),
            joinedload(Account.university_record),
        )
        .filter(Account.role == "Alumni")
    )


@router.get("")
def list_cards(
    page: int = 1,
    page_size: int = 10,
    q: str = "",
    status: str = "",
    sort_by: str = "submitted",
    sort_dir: str = "desc",
    scope: str = "",
    college: str = "",
    year: str = "",
    queue: str = "",
    id_status: str = "",
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    page = max(1, page)
    page_size = min(50, max(5, page_size))
    renewal_only = (scope or "").strip().lower() == "renewal"
    query = _card_query(db)
    if renewal_only:
        query = query.filter(_renewal_clause())
    summary = None
    years: list[str] = []
    if renewal_only:
        summary_query = _card_query(db).filter(_renewal_clause())
        known = ~_unknown_card_clause()
        claimed_count, renewal_count = _resting_counts(summary_query)
        summary = {
            "all": summary_query.count(),
            "claimed": claimed_count,
            "renewal": renewal_count,
            "requesting": summary_query.filter(known, AlumniCard.status == REQUESTING_STATUS).count(),
            "printing": summary_query.filter(known, AlumniCard.status == PRINTING_STATUS).count(),
            "printed": summary_query.filter(known, AlumniCard.status == PRINTED_STATUS).count(),
            "undefined": summary_query.filter(_unknown_card_clause()).count(),
        }
        year_rows = summary_query.with_entities(_year_expr()).distinct().all()
        years = sorted(
            {str(row[0]) for row in year_rows if row[0] and len(str(row[0])) == 4 and str(row[0]).isdigit()},
            reverse=True,
        )
    wanted = (status or "").strip()
    if wanted:
        if wanted not in CARD_META:
            raise HTTPException(status_code=400, detail="Unsupported alumni card status filter.")
        query = query.filter(AlumniCard.status == wanted)
    selected_queue = (queue or "").strip().lower()
    selected_id = (id_status or "").strip().lower()
    if selected_id == "undefined":
        query = query.filter(_unknown_card_clause())
    elif selected_id:
        raise HTTPException(status_code=400, detail="Unsupported ID status filter.")
    elif selected_queue == "claimed":
        query = query.filter(
            ~_unknown_card_clause(),
            AlumniCard.status.in_((CLAIMED_STATUS, FOR_RENEWAL_STATUS)),
        )
    elif selected_queue == "requesting":
        query = query.filter(~_unknown_card_clause(), AlumniCard.status == REQUESTING_STATUS)
    elif selected_queue == "printing":
        query = query.filter(~_unknown_card_clause(), AlumniCard.status == PRINTING_STATUS)
    elif selected_queue == "printed":
        query = query.filter(~_unknown_card_clause(), AlumniCard.status == PRINTED_STATUS)
    elif selected_queue == "undefined":
        query = query.filter(_unknown_card_clause())
    elif selected_queue == "renewal":
        query = query.filter(
            ~_unknown_card_clause(),
            AlumniCard.status.in_((CLAIMED_STATUS, FOR_RENEWAL_STATUS)),
        )
    elif selected_queue:
        raise HTTPException(status_code=400, detail="Unsupported alumni card queue filter.")
    selected_college = (college or "").strip()
    if selected_college:
        query = query.filter(_college_expr() == selected_college)
    selected_year = (year or "").strip()
    if selected_year:
        query = query.filter(_year_expr() == selected_year)
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            or_(
                Account.personal_email.ilike(like),
                Account.linked_student_id.ilike(like),
                AlumniProfile.first_name.ilike(like),
                AlumniProfile.middle_name.ilike(like),
                AlumniProfile.last_name.ilike(like),
            )
        )
    key = (sort_by or "submitted").lower()
    descending = (sort_dir or "desc").lower() != "asc"
    if key == "name":
        order_col = func.lower(func.coalesce(AlumniProfile.last_name, Account.personal_email))
    elif key == "email":
        order_col = func.lower(Account.personal_email)
    else:
        order_col = AlumniCard.submitted_at
    query = query.order_by(order_col.desc() if descending else order_col.asc(), Account.id.desc())
    if selected_queue in {"claimed", "renewal"}:
        target = FOR_RENEWAL_STATUS if selected_queue == "renewal" else CLAIMED_STATUS
        matched = [row for row in query.all() if _shown_for(row) == target]
        total = len(matched)
        rows = matched[(page - 1) * page_size: page * page_size]
    else:
        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()
    counts = dict(
        db.query(AlumniCard.status, func.count(AlumniCard.id))
        .join(Account, Account.id == AlumniCard.account_id)
        .filter(Account.role == "Alumni")
        .group_by(AlumniCard.status)
        .all()
    )
    return {
        "items": [_serialize_item(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "q": term,
        "status": wanted,
        "counts": counts,
        "summary": summary,
        "years": years,
        "sort_by": key if key in {"name", "email", "submitted"} else "submitted",
        "sort_dir": "desc" if descending else "asc",
    }


@router.get("/slots")
def list_appointment_slots(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    from app.models import AacAppointmentSlot
    from app.services.alumni_hub import _booked_count

    rows = (
        db.query(AacAppointmentSlot)
        .order_by(AacAppointmentSlot.slot_date, AacAppointmentSlot.slot_time)
        .all()
    )
    return {
        "slots": [
            {
                "id": row.id,
                "date": row.slot_date.isoformat(),
                "time": row.slot_time,
                "capacity": row.capacity,
                "booked": _booked_count(db, row.slot_date, row.slot_time),
                "active": row.active,
            }
            for row in rows
            if row.active and row.slot_date >= date.today()
        ]
    }


@router.post("/slots")
def add_appointment_slot(
    payload: AppointmentSlotIn,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.models import AacAppointmentSlot

    existing = (
        db.query(AacAppointmentSlot)
        .filter(AacAppointmentSlot.slot_date == payload.slot_date, AacAppointmentSlot.slot_time == payload.slot_time)
        .first()
    )
    if existing:
        existing.capacity = payload.capacity
        existing.active = True
        row = existing
    else:
        row = AacAppointmentSlot(slot_date=payload.slot_date, slot_time=payload.slot_time, capacity=payload.capacity, active=True)
        db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "date": row.slot_date.isoformat(), "time": row.slot_time, "capacity": row.capacity, "active": row.active}


@router.delete("/slots/{slot_id}")
def remove_appointment_slot(slot_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    from app.models import AacAppointmentSlot

    row = db.get(AacAppointmentSlot, slot_id)
    if not row:
        raise HTTPException(status_code=404, detail="Appointment slot not found.")
    row.active = False
    db.commit()
    return {"ok": True}


@router.get("/{account_id}")
def card_detail(account_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    user = (
        db.query(Account)
        .options(joinedload(Account.profile), joinedload(Account.alumni_card), joinedload(Account.university_record))
        .filter(Account.id == account_id, Account.role == "Alumni")
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Alumni account not found.")
    card = serialize_card(user.alumni_card)
    academic = _academic(user)
    claimed = card["status"] == "Claimed"
    renewal = _assessment(user, academic["year_graduated"], card.get("issued_at"))
    application = _application(user)
    return {
        "account": {
            "id": user.id,
            "email": user.personal_email,
            "name": _account_name(user),
            "student_id": user.linked_student_id,
            "status": user.status,
            "degree": academic["course"],
            "college": academic["college"],
            "course": academic["course"],
            "year_graduated": academic["year_graduated"],
            "phone": user.profile.phone if user.profile else "",
            "city": user.profile.city if user.profile else "",
        },
        "card": card,
        "renewal": {
            "requested_at": card.get("submitted_at"),
            "printed_at": card.get("pickup_ready_at"),
            "claimed_at": card.get("issued_at") if claimed else None,
            "claiming_date": renewal["claiming_date"],
            "expires_at": card.get("expires_at"),
            "next_renewal_on": renewal["next_renewal_on"],
            "id_status": renewal["id_status"],
            "id_note": renewal["id_note"],
            "eligibility": renewal["eligibility"],
            "eligibility_label": renewal["eligibility_label"],
            "eligibility_note": renewal["note"],
            "display_status": _display_status(card["status"], renewal["id_status"], application, renewal),
        },
        "actions": _renewal_actions(card["status"], application, renewal["id_status"], renewal),
        "next_statuses": list(CARD_TRANSITIONS.get(card["status"], ())),
        "labels": {key: meta["label"] for key, meta in CARD_META.items()},
    }


@router.post("/{account_id}/status")
def update_card_status(
    account_id: int,
    payload: CardStatusIn,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = (
        db.query(Account)
        .options(joinedload(Account.profile), joinedload(Account.alumni_card), joinedload(Account.university_record))
        .filter(Account.id == account_id, Account.role == "Alumni")
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Alumni account not found.")
    if user.status != "Active":
        raise HTTPException(status_code=400, detail="Only Active alumni can have an alumni card processed.")
    previous = user.alumni_card
    old = canonical_card_status(previous)
    old_printed = _stamp(previous.pickup_ready_at if previous else None)
    old_claimed = _stamp(previous.issued_at if previous else None)
    application = _application(user)
    academic = _academic(user)
    renewal = _assessment(user, academic["year_graduated"], previous.issued_at if previous else None)
    membership = str(application.get("membership_type") or "")
    office_placement = (
        _status_unknown(renewal["id_status"], application)
        and membership == "Renewal"
        and payload.status in OFFICE_STEPS
    )
    card, already = transition_alumni_card_status(
        db,
        user,
        payload.status,
        pickup_location=payload.pickup_location,
        card_number=payload.card_number,
        note=payload.note,
        claimed_on=payload.claimed_on,
        office_placement=office_placement,
    )
    if renewal["id_status"] != "Defined" and membership == "Renewal":
        _remember_office_status(card, canonical_card_status(card))
        if already:
            db.commit()
    if not already:
        _log(
            db,
            admin.id,
            "AAC_STATUS",
            user.id,
            {
                "status": old,
                "printed_at": old_printed,
                "claimed_at": old_claimed,
            },
            {
                "status": canonical_card_status(card),
                "note": payload.note or "",
                "printed_at": _stamp(card.pickup_ready_at),
                "claimed_at": _stamp(card.issued_at),
                "claimed_on": payload.claimed_on.isoformat() if payload.claimed_on else None,
            },
        )
        db.commit()
        meta = CARD_META[canonical_card_status(card)]
        note = (payload.note or "").strip()
        try:
            send_notice(
                db,
                kind="aac_status",
                to_address=user.personal_email,
                account_id=user.id,
                name=_account_name(user),
                subject="Alumni card status",
                headline=meta["headline"],
                intro=f"Your Angelenean Alumni Card status is now {meta['label']}.",
                detail=" ".join(part for part in [meta["next"], note] if part),
                path="/alumni/card",
                cta="Open your alumni card",
            )
            db.commit()
        except Exception:
            logger.exception("Alumni card status email failed")
            db.rollback()
    fresh = serialize_card(card)
    return {
        "ok": True,
        "already_processed": already,
        "card": fresh,
        "next_statuses": list(CARD_TRANSITIONS.get(fresh["status"], ())),
    }

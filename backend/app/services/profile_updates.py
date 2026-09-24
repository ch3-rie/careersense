"""Admin-requested alumni profile updates. Does not edit alumni-owned fields."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import (
    Account,
    AdminLog,
    AlumniNotification,
    AlumniProfile,
    ProfileUpdateRequest,
    ProfileUpdateRequestRecipient,
)
from app.services.email import app_url, send_profile_update_email
from app.services.email.outbox import enqueue_if_retryable
from app.services.email.render import render_profile_update
from app.services.profile_completion import (
    field_is_present,
    field_satisfied,
    field_snapshot,
    profile_completion_percent,
)

ALLOWED_FIELDS = [
    {"id": "contact", "label": "Contact information", "target": "/alumni#contact"},
    {"id": "phone", "label": "Phone number", "target": "/alumni#contact"},
    {"id": "city", "label": "City", "target": "/alumni#contact"},
    {"id": "country", "label": "Country", "target": "/alumni#contact"},
    {"id": "profile_photo", "label": "Profile photo", "target": "/alumni"},
    {"id": "employment", "label": "Employment information", "target": "/alumni/resume"},
    {"id": "work_history", "label": "Work history", "target": "/alumni#work-history"},
    {"id": "current_occupation", "label": "Current occupation", "target": "/alumni/resume"},
    {"id": "education", "label": "Education information", "target": "/alumni"},
    {"id": "further_studies", "label": "Further studies", "target": "/alumni/resume"},
    {"id": "graduate_tracer", "label": "Graduate Tracer Survey", "target": "/alumni/resume"},
    {"id": "alumni_card", "label": "Alumni Card information", "target": "/alumni/card"},
    {"id": "other", "label": "Other profile information", "target": "/alumni"},
]
FIELD_BY_ID = {item["id"]: item for item in ALLOWED_FIELDS}
ALLOWED_TARGETS = {
    "/alumni",
    "/alumni#profile",
    "/alumni#contact",
    "/alumni#work-history",
    "/alumni/resume",
    "/alumni/card",
    "/alumni/account",
}
DEFAULT_SUBJECT = "Action Required: Please Update Your CareerSense Profile"
DEFAULT_MESSAGE = (
    "Dear Alumni,\n\n"
    "Our records indicate that some information in your CareerSense profile may need to be updated.\n\n"
    "Please review and update the requested items so that your alumni record remains accurate and up to date.\n\n"
    "Thank you for helping us maintain accurate alumni records."
)
MAX_RECIPIENTS = 200
DUPLICATE_HOURS = 24
NOTIFICATION_CATEGORY = "profile_update"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _office_name() -> str:
    return get_settings().oaaps_office_name or "Office of Alumni Affairs and Placement Services"


def field_options() -> list[dict]:
    return [dict(item) for item in ALLOWED_FIELDS]


def field_labels(field_ids: Iterable[str], other_detail: str = "") -> list[str]:
    labels = []
    for field_id in field_ids:
        item = FIELD_BY_ID.get(field_id)
        if not item:
            continue
        if field_id == "other" and other_detail.strip():
            labels.append(f"Other: {other_detail.strip()}")
        else:
            labels.append(item["label"])
    return labels


def derive_target(field_ids: list[str], requested: str = "") -> str:
    target = (requested or "").strip()
    if target in ALLOWED_TARGETS:
        return target
    routes = {FIELD_BY_ID[field_id]["target"] for field_id in field_ids if field_id in FIELD_BY_ID}
    if len(routes) == 1:
        return next(iter(routes))
    return "/alumni"


def action_url(target: str) -> str:
    path = target if target in ALLOWED_TARGETS else "/alumni"
    return app_url(path)


def alumni_display_name(account: Account) -> str:
    profile = account.profile
    if profile:
        name = " ".join(part for part in [profile.first_name, profile.middle_name, profile.last_name] if part).strip()
        if name:
            return name
    name = " ".join(part for part in [account.first_name, account.last_name] if part).strip()
    return name or account.personal_email


def normalize_fields(raw: list[str], other_detail: str) -> tuple[list[str], str]:
    seen = []
    for item in raw or []:
        key = str(item or "").strip()
        if key in FIELD_BY_ID and key not in seen:
            seen.append(key)
    if not seen:
        raise HTTPException(status_code=400, detail="Select at least one profile area to update.")
    detail = (other_detail or "").strip()
    if "other" in seen:
        if len(detail) < 3:
            raise HTTPException(status_code=400, detail="Describe the other profile information that needs updating.")
        if len(detail) > 400:
            raise HTTPException(status_code=400, detail="The other-information note must be 400 characters or fewer.")
    else:
        detail = ""
    return seen, detail


def notification_body(field_ids: list[str], other_detail: str, message: str) -> str:
    labels = field_labels(field_ids, other_detail)
    lines = ["Your CareerSense profile needs to be updated.", "", "Please review your:"]
    lines.extend(f"• {label}" for label in labels)
    if message.strip():
        lines.extend(["", "Message from AAPS:", message.strip()])
    lines.extend(["", "Select this notice to open Update My Profile."])
    return "\n".join(lines)


def load_eligible_alumni(db: Session, alumni_ids: list[int]) -> list[Account]:
    unique_ids = []
    for item in alumni_ids:
        if item not in unique_ids:
            unique_ids.append(item)
    if not unique_ids:
        raise HTTPException(status_code=400, detail="Select at least one alumni account.")
    if len(unique_ids) > MAX_RECIPIENTS:
        raise HTTPException(status_code=400, detail=f"Select at most {MAX_RECIPIENTS} alumni in one request.")
    rows = (
        db.query(Account)
        .options(joinedload(Account.profile), joinedload(Account.alumni_card))
        .filter(Account.id.in_(unique_ids), Account.role == "Alumni")
        .all()
    )
    by_id = {row.id: row for row in rows}
    missing = [item for item in unique_ids if item not in by_id]
    if missing:
        raise HTTPException(status_code=400, detail="One or more alumni accounts were not found.")
    ineligible = [row for row in rows if row.status != "Active"]
    if ineligible:
        raise HTTPException(
            status_code=400,
            detail="Profile update requests can only be sent to Active alumni accounts.",
        )
    return [by_id[item] for item in unique_ids]


def find_duplicates(db: Session, alumni_ids: list[int], field_ids: list[str]) -> list[dict]:
    since = _now() - timedelta(hours=DUPLICATE_HOURS)
    wanted = list(field_ids)
    rows = (
        db.query(ProfileUpdateRequestRecipient)
        .join(ProfileUpdateRequest)
        .options(joinedload(ProfileUpdateRequestRecipient.alumni).joinedload(Account.profile))
        .filter(
            ProfileUpdateRequestRecipient.alumni_id.in_(alumni_ids),
            ProfileUpdateRequest.created_at >= since,
        )
        .all()
    )
    found = []
    for row in rows:
        previous = list(row.request.requested_fields or [])
        if previous == wanted:
            alumni = row.alumni
            found.append(
                {
                    "alumni_id": row.alumni_id,
                    "name": alumni_display_name(alumni) if alumni else "",
                    "email": alumni.personal_email if alumni else row.email,
                    "sent_at": row.request.created_at,
                }
            )
    return found


def _recipient_status(row: ProfileUpdateRequestRecipient) -> str:
    if row.completed_at:
        return "Updated"
    if row.viewed_at:
        return "Viewed"
    return "Not yet updated"


def _request_status(request: ProfileUpdateRequest) -> str:
    recipients = request.recipients or []
    if recipients and all(row.completed_at for row in recipients):
        return "Completed"
    if request.email_failed_count and not request.email_sent_count:
        return "Failed"
    if request.email_failed_count:
        return "Partially Sent"
    return "Sent"


def serialize_recipient(row: ProfileUpdateRequestRecipient, current: dict | None = None) -> dict:
    alumni = row.alumni
    snapshot = current if current is not None else (row.baseline_json or {})
    fields = list(row.request.requested_fields or []) if row.request else []
    tracked = [field_id for field_id in fields if field_id != "other"]
    return {
        "id": row.id,
        "alumni_id": row.alumni_id,
        "name": alumni_display_name(alumni) if alumni else "",
        "email": row.email,
        "student_id": alumni.linked_student_id if alumni else "",
        "email_status": row.email_status,
        "email_sent_at": row.email_sent_at,
        "email_error": row.email_error,
        "viewed_at": row.viewed_at,
        "completed_at": row.completed_at,
        "status": _recipient_status(row),
        "fields": [
            {
                "id": field_id,
                "label": FIELD_BY_ID.get(field_id, {}).get("label", field_id),
                "complete": (
                    field_is_present(field_id, snapshot)
                    if row.completed_at
                    else field_satisfied(field_id, row.baseline_json or {}, snapshot)
                ),
            }
            for field_id in tracked
        ],
    }


def serialize_request(row: ProfileUpdateRequest) -> dict:
    admin = row.admin
    recipients = row.recipients or []
    return {
        "id": row.id,
        "created_at": row.created_at,
        "subject": row.subject,
        "message": row.message,
        "requested_fields": list(row.requested_fields or []),
        "requested_labels": field_labels(row.requested_fields or [], row.other_detail),
        "other_detail": row.other_detail or "",
        "target_route": row.target_route,
        "status": _request_status(row),
        "sent_by": alumni_display_name(admin) if admin else "",
        "sent_by_email": admin.personal_email if admin else "",
        "recipient_count": row.recipient_count,
        "email_sent_count": row.email_sent_count,
        "email_failed_count": row.email_failed_count,
        "email_status": (
            "Failed"
            if row.email_failed_count and not row.email_sent_count
            else "Partially sent"
            if row.email_failed_count
            else "Sent"
        ),
        "completed_count": sum(1 for item in recipients if item.completed_at),
        "viewed_count": sum(1 for item in recipients if item.viewed_at),
    }


def serialize_request_detail(db: Session, row: ProfileUpdateRequest) -> dict:
    payload = serialize_request(row)
    payload["recipients"] = []
    for item in row.recipients or []:
        current = field_snapshot(db, item.alumni) if item.alumni else (item.baseline_json or {})
        payload["recipients"].append(serialize_recipient(item, current))
    return payload


def evaluate_profile_update_completions(db: Session, user: Account) -> None:
    open_rows = (
        db.query(ProfileUpdateRequestRecipient)
        .join(ProfileUpdateRequest)
        .options(joinedload(ProfileUpdateRequestRecipient.request))
        .filter(
            ProfileUpdateRequestRecipient.alumni_id == user.id,
            ProfileUpdateRequestRecipient.completed_at.is_(None),
        )
        .all()
    )
    if not open_rows:
        return
    current = field_snapshot(db, user)
    now = _now()
    dirty = False
    for row in open_rows:
        fields = [field_id for field_id in (row.request.requested_fields or []) if field_id != "other"]
        if not fields:
            continue
        if all(field_satisfied(field_id, row.baseline_json or {}, current) for field_id in fields):
            row.completed_at = now
            if row.notification_id:
                note = db.get(AlumniNotification, row.notification_id)
                if note and note.account_id == user.id and note.read_at is None:
                    note.read_at = now
            dirty = True
    if dirty:
        db.commit()


def mark_request_viewed(db: Session, notification_id: int, account_id: int) -> None:
    row = (
        db.query(ProfileUpdateRequestRecipient)
        .filter(
            ProfileUpdateRequestRecipient.notification_id == notification_id,
            ProfileUpdateRequestRecipient.alumni_id == account_id,
        )
        .first()
    )
    if row and row.viewed_at is None:
        row.viewed_at = _now()


def composer_defaults() -> dict:
    return {
        "fields": field_options(),
        "default_subject": DEFAULT_SUBJECT,
        "default_message": DEFAULT_MESSAGE,
        "max_recipients": MAX_RECIPIENTS,
        "duplicate_hours": DUPLICATE_HOURS,
    }


def search_alumni(
    db: Session,
    *,
    q: str = "",
    year: str = "",
    degree: str = "",
    completion: str = "",
    page: int = 1,
    page_size: int = 10,
) -> dict:
    page = max(1, page)
    page_size = min(50, max(5, page_size))
    query = (
        db.query(Account)
        .outerjoin(AlumniProfile, AlumniProfile.account_id == Account.id)
        .options(joinedload(Account.profile), joinedload(Account.university_record), joinedload(Account.alumni_card))
        .filter(Account.role == "Alumni", Account.status == "Active")
    )
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            or_(
                Account.personal_email.ilike(like),
                Account.linked_student_id.ilike(like),
                AlumniProfile.first_name.ilike(like),
                AlumniProfile.last_name.ilike(like),
                AlumniProfile.middle_name.ilike(like),
            )
        )
    if year.strip():
        query = query.filter(AlumniProfile.year_graduated == year.strip())
    if degree.strip():
        query = query.filter(AlumniProfile.degree.ilike(f"%{degree.strip()}%"))

    needs_score = (completion or "").strip().lower()
    if needs_score:
        scored = []
        for user in query.order_by(AlumniProfile.last_name.asc(), Account.id.asc()).all():
            snapshot = field_snapshot(db, user)
            percent = profile_completion_percent(snapshot)
            if needs_score in {"incomplete", "below-100"} and percent >= 100:
                continue
            if needs_score == "90-100" and not (90 <= percent <= 100):
                continue
            if needs_score == "70-89" and not (70 <= percent <= 89):
                continue
            if needs_score in {"below-70", "below_70"} and percent >= 70:
                continue
            scored.append((user, snapshot, percent))
        total = len(scored)
        start = (page - 1) * page_size
        page_rows = scored[start : start + page_size]
    else:
        total = query.count()
        rows = (
            query.order_by(AlumniProfile.last_name.asc(), Account.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        page_rows = []
        for user in rows:
            snapshot = field_snapshot(db, user)
            page_rows.append((user, snapshot, profile_completion_percent(snapshot)))

    items = []
    for user, snapshot, percent in page_rows:
        profile = user.profile
        items.append(
            {
                "id": user.id,
                "name": alumni_display_name(user),
                "email": user.personal_email,
                "student_id": user.linked_student_id or "",
                "degree": profile.degree if profile else "",
                "year_graduated": profile.year_graduated if profile else "",
                "status": user.status,
                "completion_percent": percent,
                "last_updated": profile.updated_at if profile else user.updated_at,
                "has_photo": bool(snapshot.get("photo_path")),
                "has_phone": bool(snapshot.get("phone")),
                "has_tracer": bool(snapshot.get("has_tracer")),
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_requests(db: Session, page: int = 1, page_size: int = 10) -> dict:
    page = max(1, page)
    page_size = min(50, max(5, page_size))
    query = db.query(ProfileUpdateRequest).options(
        joinedload(ProfileUpdateRequest.admin),
        joinedload(ProfileUpdateRequest.recipients),
    )
    total = query.count()
    rows = (
        query.order_by(ProfileUpdateRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [serialize_request(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        **composer_defaults(),
    }


def get_request(db: Session, request_id: int) -> dict:
    row = (
        db.query(ProfileUpdateRequest)
        .options(
            joinedload(ProfileUpdateRequest.admin),
            joinedload(ProfileUpdateRequest.recipients).joinedload(ProfileUpdateRequestRecipient.alumni).joinedload(Account.profile),
        )
        .filter(ProfileUpdateRequest.id == request_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Profile update request not found.")
    return serialize_request_detail(db, row)


def create_request(db: Session, admin: Account, payload) -> dict:
    field_ids, other_detail = normalize_fields(payload.requested_fields, payload.other_detail)
    subject = (payload.subject or "").strip() or DEFAULT_SUBJECT
    message = (payload.message or "").strip()
    if len(message) < 10:
        raise HTTPException(status_code=400, detail="Write a short instruction for alumni.")
    alumni = load_eligible_alumni(db, payload.alumni_ids)
    duplicates = find_duplicates(db, [row.id for row in alumni], field_ids)
    if duplicates and not payload.force_resend:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"{len(duplicates)} selected alumni already received this request in the last "
                    f"{DUPLICATE_HOURS} hours. Confirm if you want to send it again."
                ),
                "duplicates": [
                    {
                        "alumni_id": item["alumni_id"],
                        "name": item["name"],
                        "email": item["email"],
                        "sent_at": item["sent_at"].isoformat() if item["sent_at"] else None,
                    }
                    for item in duplicates
                ],
            },
        )
    target = derive_target(field_ids, payload.target)
    request = ProfileUpdateRequest(
        created_by=admin.id,
        subject=subject[:200],
        message=message[:2000],
        requested_fields=field_ids,
        other_detail=other_detail,
        target_route=target,
        status="Sent",
        recipient_count=len(alumni),
    )
    db.add(request)
    db.flush()

    sent = 0
    failed = 0
    disabled = 0
    body = notification_body(field_ids, other_detail, message)
    title = subject[:200]
    for user in alumni:
        note = AlumniNotification(
            account_id=user.id,
            title=title,
            body=body,
            category=NOTIFICATION_CATEGORY,
            link=target,
        )
        db.add(note)
        db.flush()
        snapshot = field_snapshot(db, user)
        result = send_profile_update_email(
            to_address=user.personal_email,
            name=alumni_display_name(user),
            subject=subject[:200],
            message=message.strip(),
            fields=field_labels(field_ids, other_detail),
            action_url=action_url(target),
        )
        if result.ok:
            email_status = "sent"
        elif result.disabled:
            email_status = "disabled"
        else:
            email_status = "failed"
        recipient = ProfileUpdateRequestRecipient(
            request_id=request.id,
            alumni_id=user.id,
            notification_id=note.id,
            email=user.personal_email,
            email_status=email_status,
            email_sent_at=_now() if result.ok else None,
            email_error="" if result.ok else (result.error or "The email could not be sent.")[:400],
            baseline_json=snapshot,
        )
        db.add(recipient)
        db.flush()
        if email_status == "failed":
            labels = field_labels(field_ids, other_detail)
            text_body, html_body = render_profile_update(
                name=alumni_display_name(user),
                office=_office_name(),
                message=message.strip(),
                fields=labels,
                action_url=action_url(target),
            )
            enqueue_if_retryable(
                db,
                result,
                kind="profile_update",
                to_address=user.personal_email,
                subject=subject[:200],
                text_body=text_body,
                html_body=html_body,
                account_id=user.id,
                meta={"recipient_id": recipient.id, "request_id": request.id},
            )
        if result.ok:
            sent += 1
        elif result.disabled:
            disabled += 1
        else:
            failed += 1

    request.email_sent_count = sent
    request.email_failed_count = failed + disabled
    if sent and not failed and not disabled:
        request.status = "Sent"
    elif sent:
        request.status = "Partially Sent"
    else:
        request.status = "Failed"
    db.add(
        AdminLog(
            admin_id=admin.id,
            action_type="profile_update_request",
            target_id=str(request.id),
            new_value={
                "recipient_count": len(alumni),
                "alumni_ids": [row.id for row in alumni],
                "requested_fields": field_ids,
                "subject": subject[:200],
                "notification_type": NOTIFICATION_CATEGORY,
                "email_sent": sent,
                "email_failed": failed,
                "email_disabled": disabled,
            },
        )
    )
    db.commit()
    detail = get_request(db, request.id)
    if disabled and not sent and not failed:
        email_summary = "Email sending is disabled on this server, so no messages were delivered."
    else:
        email_summary = (
            f"{sent} email{'s' if sent != 1 else ''} sent successfully. "
            f"{failed + disabled} email{'s' if (failed + disabled) != 1 else ''} failed."
        )
    detail["message_summary"] = (
        f"{len(alumni)} in-system notification{'s' if len(alumni) != 1 else ''} created. {email_summary}"
    )
    return detail

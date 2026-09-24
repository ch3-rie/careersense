"""Admin-configured automated profile-update reminder emails."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings as get_app_settings
from app.models import (
    Account,
    AdminLog,
    AlumniNotification,
    AlumniProfile,
    ProfileReminderRun,
    ProfileReminderSend,
    ProfileReminderSettings,
    ProfileUpdateRequestRecipient,
)
from app.services.email import email_health, scheduler_is_enabled, send_profile_update_email
from app.services.email.clock import aware, campus_tz, now_utc
from app.services.email.outbox import enqueue_if_retryable
from app.services.email.render import render_profile_update
from app.services.profile_completion import field_is_present, field_snapshot, profile_completion_percent
from app.services.profile_updates import (
    DEFAULT_SUBJECT,
    action_url,
    alumni_display_name,
    composer_defaults,
    derive_target,
    field_labels,
    load_eligible_alumni,
    normalize_fields,
    notification_body,
)
from app.services.profile_updates import _office_name

logger = logging.getLogger("careersense")

SETTINGS_ID = 1
FREQUENCIES = ("daily", "weekly", "monthly", "interval")
TARGET_MODES = ("all_active", "incomplete", "filtered", "selected")
WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
MAX_AUTO_RECIPIENTS = 2000
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LOCK_MINUTES = 30


def _default_message() -> str:
    return (
        "Dear Alumni,\n\n"
        "This is a scheduled reminder from the Office of Alumni Affairs and Placement Services "
        "to review and update your CareerSense profile.\n\n"
        "Please keep your contact and employment information current so OAAPS can support alumni services.\n\n"
        "Thank you."
    )


def get_settings_row(db: Session) -> ProfileReminderSettings:
    row = db.get(ProfileReminderSettings, SETTINGS_ID)
    if row:
        return row
    row = ProfileReminderSettings(
        id=SETTINGS_ID,
        enabled=False,
        frequency="weekly",
        interval_days=14,
        send_hour=9,
        send_weekday=0,
        send_day_of_month=1,
        target_mode="incomplete",
        target_filters={},
        alumni_ids=[],
        subject=DEFAULT_SUBJECT,
        message=_default_message(),
        requested_fields=["contact", "employment"],
        other_detail="",
        min_days_between=14,
        skip_if_complete=True,
    )
    db.add(row)
    db.flush()
    return row


def _filters(row: ProfileReminderSettings) -> dict:
    raw = row.target_filters if isinstance(row.target_filters, dict) else {}
    return {
        "year": str(raw.get("year") or "").strip(),
        "degree": str(raw.get("degree") or "").strip(),
        "completion": str(raw.get("completion") or "").strip(),
    }


def _at_hour(day: datetime, hour: int) -> datetime:
    return day.replace(hour=hour, minute=0, second=0, microsecond=0)


def _add_month(day: datetime, month_day: int) -> datetime:
    year, month = day.year, day.month + 1
    if month > 12:
        year, month = year + 1, 1
    return day.replace(year=year, month=month, day=month_day)


def _schedule_windows(row: ProfileReminderSettings, current: datetime) -> tuple[datetime, datetime]:
    hour = max(0, min(23, int(row.send_hour or 0)))
    weekday = max(0, min(6, int(row.send_weekday or 0)))
    month_day = max(1, min(28, int(row.send_day_of_month or 1)))
    freq = (row.frequency or "weekly").strip().lower()
    if freq == "weekly":
        days_ahead = (weekday - current.weekday()) % 7
        this_slot = _at_hour(current + timedelta(days=days_ahead), hour)
        if days_ahead == 0:
            last_occ = this_slot if current >= this_slot else this_slot - timedelta(days=7)
            next_occ = this_slot if current < this_slot else this_slot + timedelta(days=7)
        else:
            last_occ = this_slot - timedelta(days=7)
            next_occ = this_slot
        return last_occ, next_occ
    if freq == "monthly":
        this_slot = _at_hour(current.replace(day=month_day), hour)
        if current >= this_slot:
            return this_slot, _at_hour(_add_month(current, month_day), hour)
        previous = current.replace(year=current.year - 1, month=12, day=month_day) if current.month == 1 else current.replace(month=current.month - 1, day=month_day)
        return _at_hour(previous, hour), this_slot
    if freq == "interval":
        days = max(1, min(365, int(row.interval_days or 14)))
        last = aware(row.last_scheduled_run_at)
        today_slot = _at_hour(current, hour)
        if last is None:
            if current < today_slot:
                return today_slot - timedelta(days=1), today_slot
            return today_slot, today_slot + timedelta(days=1)
        last_local = last.astimezone(campus_tz())
        next_occ = _at_hour(last_local + timedelta(days=days), hour)
        return next_occ - timedelta(days=days), next_occ
    today_slot = _at_hour(current, hour)
    if current >= today_slot:
        return today_slot, today_slot + timedelta(days=1)
    return today_slot - timedelta(days=1), today_slot


def _next_scheduled_at(row: ProfileReminderSettings, now: Optional[datetime] = None) -> Optional[datetime]:
    if not row.enabled:
        return None
    current = (now or now_utc()).astimezone(campus_tz())
    last_occ, next_occ = _schedule_windows(row, current)
    last_run = aware(row.last_scheduled_run_at)
    if last_run is None:
        return next_occ
    last_local = last_run.astimezone(campus_tz())
    if last_local < last_occ:
        return last_occ
    return next_occ


def reminder_is_due(row: ProfileReminderSettings, now: Optional[datetime] = None) -> bool:
    if not row.enabled:
        return False
    nxt = _next_scheduled_at(row, now)
    if nxt is None:
        return False
    current = (now or now_utc()).astimezone(campus_tz())
    return current >= nxt.astimezone(campus_tz())


def _matches_completion(percent: int, band: str) -> bool:
    key = (band or "").strip().lower()
    if not key:
        return True
    if key in {"incomplete", "below-100"}:
        return percent < 100
    if key == "90-100":
        return 90 <= percent <= 100
    if key == "70-89":
        return 70 <= percent <= 89
    if key in {"below-70", "below_70"}:
        return percent < 70
    return True


def _active_alumni_query(db: Session):
    return (
        db.query(Account)
        .outerjoin(AlumniProfile, AlumniProfile.account_id == Account.id)
        .options(joinedload(Account.profile), joinedload(Account.alumni_card))
        .filter(Account.role == "Alumni", Account.status == "Active")
    )


def resolve_candidates(db: Session, row: ProfileReminderSettings) -> list[Account]:
    mode = (row.target_mode or "incomplete").strip().lower()
    if mode not in TARGET_MODES:
        mode = "incomplete"
    if mode == "selected":
        ids = []
        for item in row.alumni_ids or []:
            try:
                value = int(item)
            except (TypeError, ValueError):
                continue
            if value not in ids:
                ids.append(value)
        if not ids:
            return []
        rows = (
            _active_alumni_query(db)
            .filter(Account.id.in_(ids[:MAX_AUTO_RECIPIENTS]))
            .all()
        )
        by_id = {item.id: item for item in rows}
        return [by_id[item] for item in ids if item in by_id]

    query = _active_alumni_query(db)
    filters = _filters(row)
    if mode == "filtered":
        if filters["year"]:
            query = query.filter(AlumniProfile.year_graduated == filters["year"])
        if filters["degree"]:
            query = query.filter(AlumniProfile.degree.ilike(f"%{filters['degree']}%"))
    rows = query.order_by(AlumniProfile.last_name.asc(), Account.id.asc()).all()
    selected = []
    for user in rows:
        if not _EMAIL_RE.match((user.personal_email or "").strip()):
            continue
        snapshot = field_snapshot(db, user)
        percent = profile_completion_percent(snapshot)
        if mode == "incomplete" and percent >= 100:
            continue
        if mode == "filtered" and not _matches_completion(percent, filters["completion"]):
            continue
        selected.append(user)
        if len(selected) >= MAX_AUTO_RECIPIENTS:
            break
    return selected


def _recently_emailed(db: Session, alumni_id: int, since: datetime) -> bool:
    reminder = (
        db.query(ProfileReminderSend)
        .filter(
            ProfileReminderSend.alumni_id == alumni_id,
            ProfileReminderSend.email_status == "sent",
            ProfileReminderSend.sent_at >= since,
        )
        .first()
    )
    if reminder:
        return True
    manual = (
        db.query(ProfileUpdateRequestRecipient)
        .filter(
            ProfileUpdateRequestRecipient.alumni_id == alumni_id,
            ProfileUpdateRequestRecipient.email_status == "sent",
            ProfileUpdateRequestRecipient.email_sent_at >= since,
        )
        .first()
    )
    return bool(manual)


def _fields_already_complete(db: Session, user: Account, field_ids: list[str]) -> bool:
    tracked = [field_id for field_id in field_ids if field_id != "other"]
    if not tracked:
        return False
    snapshot = field_snapshot(db, user)
    return all(field_is_present(field_id, snapshot) for field_id in tracked)


def _snapshot_settings(row: ProfileReminderSettings) -> dict:
    return {
        "enabled": row.enabled,
        "frequency": row.frequency,
        "interval_days": row.interval_days,
        "send_hour": row.send_hour,
        "send_weekday": row.send_weekday,
        "send_day_of_month": row.send_day_of_month,
        "target_mode": row.target_mode,
        "target_filters": _filters(row),
        "alumni_ids": list(row.alumni_ids or []),
        "subject": row.subject,
        "requested_fields": list(row.requested_fields or []),
        "min_days_between": row.min_days_between,
        "skip_if_complete": row.skip_if_complete,
    }


def serialize_settings(db: Session, row: Optional[ProfileReminderSettings] = None) -> dict:
    row = row or get_settings_row(db)
    latest = (
        db.query(ProfileReminderRun)
        .order_by(ProfileReminderRun.started_at.desc())
        .first()
    )
    nxt = _next_scheduled_at(row)
    return {
        "enabled": bool(row.enabled),
        "frequency": row.frequency,
        "interval_days": row.interval_days,
        "send_hour": row.send_hour,
        "send_weekday": row.send_weekday,
        "send_day_of_month": row.send_day_of_month,
        "target_mode": row.target_mode,
        "target_filters": _filters(row),
        "alumni_ids": list(row.alumni_ids or []),
        "subject": row.subject or DEFAULT_SUBJECT,
        "message": row.message or _default_message(),
        "requested_fields": list(row.requested_fields or []),
        "other_detail": row.other_detail or "",
        "min_days_between": row.min_days_between,
        "skip_if_complete": bool(row.skip_if_complete),
        "updated_at": row.updated_at,
        "last_run_at": row.last_run_at,
        "last_scheduled_run_at": row.last_scheduled_run_at,
        "next_run_at": nxt.isoformat() if nxt else None,
        "timezone": (get_app_settings().email_timezone or "Asia/Manila").strip() or "Asia/Manila",
        "last_run": serialize_run(latest) if latest else None,
        "weekdays": [{"id": index, "label": label} for index, label in enumerate(WEEKDAYS)],
        "frequencies": [
            {"id": "daily", "label": "Every day"},
            {"id": "weekly", "label": "Every week"},
            {"id": "monthly", "label": "Every month"},
            {"id": "interval", "label": "Every N days"},
        ],
        "target_modes": [
            {"id": "all_active", "label": "All Active alumni"},
            {"id": "incomplete", "label": "Active alumni with incomplete profiles"},
            {"id": "filtered", "label": "Filter by year, program, or completion"},
            {"id": "selected", "label": "Selected alumni"},
        ],
        "max_auto_recipients": MAX_AUTO_RECIPIENTS,
        "email_scheduler": scheduler_is_enabled(),
        **composer_defaults(),
        **email_health(),
    }


def serialize_run(row: Optional[ProfileReminderRun]) -> Optional[dict]:
    if not row:
        return None
    return {
        "id": row.id,
        "triggered_by": row.triggered_by,
        "status": row.status,
        "candidate_count": row.candidate_count,
        "sent_count": row.sent_count,
        "failed_count": row.failed_count,
        "skipped_count": row.skipped_count,
        "disabled_count": row.disabled_count,
        "error": row.error or "",
        "started_at": row.started_at,
        "finished_at": row.finished_at,
    }


def serialize_run_detail(db: Session, run_id: int) -> dict:
    row = (
        db.query(ProfileReminderRun)
        .options(joinedload(ProfileReminderRun.sends).joinedload(ProfileReminderSend.alumni).joinedload(Account.profile))
        .filter(ProfileReminderRun.id == run_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Reminder run not found.")
    payload = serialize_run(row) or {}
    payload["recipients"] = [
        {
            "id": item.id,
            "alumni_id": item.alumni_id,
            "name": alumni_display_name(item.alumni) if item.alumni else "",
            "email": item.email,
            "email_status": item.email_status,
            "skipped_reason": item.skipped_reason,
            "email_error": item.email_error,
            "sent_at": item.sent_at,
        }
        for item in row.sends or []
    ]
    return payload


def list_runs(db: Session, page: int = 1, page_size: int = 10) -> dict:
    page = max(1, page)
    page_size = min(50, max(5, page_size))
    query = db.query(ProfileReminderRun)
    total = query.count()
    rows = (
        query.order_by(ProfileReminderRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": [serialize_run(row) for row in rows], "total": total, "page": page, "page_size": page_size}


def validate_and_apply(db: Session, row: ProfileReminderSettings, payload) -> ProfileReminderSettings:
    enabled = bool(payload.enabled)
    frequency = str(payload.frequency or "weekly").strip().lower()
    if frequency not in FREQUENCIES:
        raise HTTPException(status_code=400, detail="Choose a valid reminder frequency.")
    target_mode = str(payload.target_mode or "incomplete").strip().lower()
    if target_mode not in TARGET_MODES:
        raise HTTPException(status_code=400, detail="Choose a valid alumni target.")
    fields, other_detail = normalize_fields(payload.requested_fields, payload.other_detail)
    subject = (payload.subject or "").strip() or DEFAULT_SUBJECT
    message = (payload.message or "").strip()
    if enabled and len(message) < 10:
        raise HTTPException(status_code=400, detail="Write the reminder message alumni will receive.")
    if not message:
        message = _default_message()
    alumni_ids = []
    for item in payload.alumni_ids or []:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value not in alumni_ids:
            alumni_ids.append(value)
    if enabled and target_mode == "selected" and not alumni_ids:
        raise HTTPException(status_code=400, detail="Select at least one Active alumnus for this reminder.")
    if enabled and target_mode == "selected":
        load_eligible_alumni(db, alumni_ids)
    if len(alumni_ids) > MAX_AUTO_RECIPIENTS:
        raise HTTPException(status_code=400, detail=f"Select at most {MAX_AUTO_RECIPIENTS} alumni.")
    hour = int(payload.send_hour)
    if hour < 0 or hour > 23:
        raise HTTPException(status_code=400, detail="Send hour must be between 0 and 23 (Asia/Manila).")
    weekday = int(payload.send_weekday)
    if weekday < 0 or weekday > 6:
        raise HTTPException(status_code=400, detail="Choose a weekday between Monday and Sunday.")
    month_day = int(payload.send_day_of_month)
    if month_day < 1 or month_day > 28:
        raise HTTPException(status_code=400, detail="Monthly reminders can be scheduled on days 1 through 28.")
    interval_days = int(payload.interval_days)
    if interval_days < 1 or interval_days > 365:
        raise HTTPException(status_code=400, detail="Interval must be between 1 and 365 days.")
    min_days = int(payload.min_days_between)
    if min_days < 1 or min_days > 365:
        raise HTTPException(status_code=400, detail="Minimum days between emails must be between 1 and 365.")

    row.enabled = enabled
    row.frequency = frequency
    row.interval_days = interval_days
    row.send_hour = hour
    row.send_weekday = weekday
    row.send_day_of_month = month_day
    row.target_mode = target_mode
    row.target_filters = {
        "year": str(payload.target_year or "").strip(),
        "degree": str(payload.target_degree or "").strip(),
        "completion": str(payload.target_completion or "").strip(),
    }
    row.alumni_ids = alumni_ids
    row.subject = subject[:200]
    row.message = message[:2000]
    row.requested_fields = fields
    row.other_detail = other_detail
    row.min_days_between = min_days
    row.skip_if_complete = bool(payload.skip_if_complete)
    row.updated_at = now_utc()
    return row


def save_settings(db: Session, admin: Account, payload) -> dict:
    row = get_settings_row(db)
    old = _snapshot_settings(row)
    validate_and_apply(db, row, payload)
    row.updated_by = admin.id
    db.add(
        AdminLog(
            admin_id=admin.id,
            action_type="profile_reminder_settings",
            target_id="1",
            old_value=old,
            new_value=_snapshot_settings(row),
        )
    )
    db.commit()
    db.refresh(row)
    return serialize_settings(db, row)


def preview_recipients(db: Session, limit: int = 10) -> dict:
    row = get_settings_row(db)
    try:
        candidates = resolve_candidates(db, row)
    except HTTPException as exc:
        return {"total": 0, "items": [], "error": str(exc.detail), **serialize_settings(db, row)}
    since = now_utc() - timedelta(days=max(1, int(row.min_days_between or 14)))
    items = []
    skipped = 0
    for user in candidates:
        reason = ""
        if _recently_emailed(db, user.id, since):
            reason = "recently_emailed"
            skipped += 1
        elif row.skip_if_complete and _fields_already_complete(db, user, list(row.requested_fields or [])):
            reason = "already_complete"
            skipped += 1
        if len(items) < max(1, min(25, limit)):
            items.append(
                {
                    "id": user.id,
                    "name": alumni_display_name(user),
                    "email": user.personal_email,
                    "student_id": user.linked_student_id or "",
                    "skip_reason": reason,
                }
            )
    return {
        "total": len(candidates),
        "skipped_estimate": skipped,
        "send_estimate": max(0, len(candidates) - skipped),
        "items": items,
        **serialize_settings(db, row),
    }


def _send_one(
    db: Session,
    *,
    row: ProfileReminderSettings,
    run: ProfileReminderRun,
    user: Account,
    field_ids: list[str],
    other_detail: str,
    subject: str,
    message: str,
    target: str,
    labels: list[str],
) -> ProfileReminderSend:
    now = now_utc()
    note = AlumniNotification(
        account_id=user.id,
        title=subject[:200],
        body=notification_body(field_ids, other_detail, message),
        category="profile_update",
        link=target,
    )
    db.add(note)
    db.flush()
    result = send_profile_update_email(
        to_address=user.personal_email,
        name=alumni_display_name(user),
        subject=subject[:200],
        message=message.strip(),
        fields=labels,
        action_url=action_url(target),
    )
    if result.ok:
        status = "sent"
    elif result.disabled:
        status = "disabled"
    else:
        status = "failed"
    send = ProfileReminderSend(
        run_id=run.id,
        alumni_id=user.id,
        email=user.personal_email,
        email_status=status,
        email_error="" if result.ok else (result.error or "The email could not be sent.")[:400],
        skipped_reason="",
        notification_id=note.id,
        sent_at=now if result.ok else None,
    )
    db.add(send)
    db.flush()
    if not result.ok and not result.disabled:
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
            kind="profile_reminder",
            to_address=user.personal_email,
            subject=subject[:200],
            text_body=text_body,
            html_body=html_body,
            account_id=user.id,
            meta={"reminder_send_id": send.id, "run_id": run.id},
        )
    return send


def run_reminders(
    db: Session,
    *,
    triggered_by: str = "schedule",
    admin: Optional[Account] = None,
    force: bool = False,
) -> dict:
    row = get_settings_row(db)
    now = now_utc()
    if triggered_by == "schedule" and not reminder_is_due(row, now):
        return {"ok": True, "ran": False, "reason": "not_due"}
    if not row.enabled and triggered_by != "admin":
        return {"ok": True, "ran": False, "reason": "disabled"}
    if triggered_by == "admin" and not row.requested_fields:
        raise HTTPException(status_code=400, detail="Save the reminder fields and message before sending.")
    lock_until = aware(row.lock_until)
    if lock_until and lock_until > now:
        if triggered_by == "admin":
            raise HTTPException(status_code=409, detail="A reminder run is already in progress. Please wait a moment.")
        return {"ok": True, "ran": False, "reason": "locked"}

    row.lock_until = now + timedelta(minutes=LOCK_MINUTES)
    db.flush()

    field_ids = list(row.requested_fields or [])
    other_detail = row.other_detail or ""
    subject = (row.subject or DEFAULT_SUBJECT)[:200]
    message = (row.message or _default_message()).strip()
    target = derive_target(field_ids)
    labels = field_labels(field_ids, other_detail)
    since = now - timedelta(days=max(1, int(row.min_days_between or 14)))
    run = ProfileReminderRun(
        triggered_by=triggered_by,
        admin_id=admin.id if admin else None,
        status="running",
        settings_snapshot=_snapshot_settings(row),
        started_at=now,
    )
    db.add(run)
    db.flush()
    sent = failed = skipped = disabled = 0
    try:
        candidates = resolve_candidates(db, row)
        run.candidate_count = len(candidates)
        for user in candidates:
            if not _EMAIL_RE.match((user.personal_email or "").strip()):
                db.add(
                    ProfileReminderSend(
                        run_id=run.id,
                        alumni_id=user.id,
                        email=user.personal_email or "",
                        email_status="skipped",
                        skipped_reason="invalid_email",
                    )
                )
                skipped += 1
                continue
            if not force and _recently_emailed(db, user.id, since):
                db.add(
                    ProfileReminderSend(
                        run_id=run.id,
                        alumni_id=user.id,
                        email=user.personal_email,
                        email_status="skipped",
                        skipped_reason="recently_emailed",
                    )
                )
                skipped += 1
                continue
            if row.skip_if_complete and _fields_already_complete(db, user, field_ids):
                db.add(
                    ProfileReminderSend(
                        run_id=run.id,
                        alumni_id=user.id,
                        email=user.personal_email,
                        email_status="skipped",
                        skipped_reason="already_complete",
                    )
                )
                skipped += 1
                continue
            send = _send_one(
                db,
                row=row,
                run=run,
                user=user,
                field_ids=field_ids,
                other_detail=other_detail,
                subject=subject,
                message=message,
                target=target,
                labels=labels,
            )
            if send.email_status == "sent":
                sent += 1
            elif send.email_status == "disabled":
                disabled += 1
            else:
                failed += 1
        run.sent_count = sent
        run.failed_count = failed
        run.skipped_count = skipped
        run.disabled_count = disabled
        run.status = "completed"
        if disabled and not sent and not failed:
            run.status = "disabled"
        elif failed and not sent:
            run.status = "failed"
        elif failed:
            run.status = "partial"
        run.finished_at = now_utc()
        row.last_run_at = run.finished_at
        if triggered_by == "schedule":
            row.last_scheduled_run_at = run.finished_at
        row.lock_until = None
        db.add(
            AdminLog(
                admin_id=admin.id if admin else None,
                action_type="profile_reminder_run",
                target_id=str(run.id),
                new_value={
                    "triggered_by": triggered_by,
                    "sent": sent,
                    "failed": failed,
                    "skipped": skipped,
                    "disabled": disabled,
                    "candidates": run.candidate_count,
                },
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Profile reminder run failed")
        row = get_settings_row(db)
        row.lock_until = None
        failed_run = db.get(ProfileReminderRun, run.id)
        if failed_run:
            failed_run.status = "failed"
            failed_run.error = "The reminder run could not be completed."[:400]
            failed_run.finished_at = now_utc()
        db.commit()
        if triggered_by == "admin":
            raise HTTPException(status_code=500, detail="The reminder run could not be completed.") from exc
        return {"ok": False, "ran": True, "reason": "error"}
    return {
        "ok": True,
        "ran": True,
        "run": serialize_run_detail(db, run.id),
        "settings": serialize_settings(db),
    }


def maybe_run_due_reminders(db: Session) -> dict:
    row = get_settings_row(db)
    db.commit()
    db.refresh(row)
    if not row.enabled or not reminder_is_due(row):
        return {"ok": True, "ran": False}
    return run_reminders(db, triggered_by="schedule")

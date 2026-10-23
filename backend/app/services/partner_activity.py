"""Partner scans, visits, and benefit redemptions.

A QR scan is recorded only when an administrator submits a token through the
partner scan endpoint. Opening or downloading an alumni QR does not create one.
A scan does not create a visit or a redemption.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models import Account, AdminLog, AlumniPerk, AlumniProfile, PartnerActivity, UniversityRecord
from app.services.alumni_qr import account_id_from_token

MANILA = ZoneInfo("Asia/Manila")
SCAN = "qr_scan"
VISIT = "partner_visit"
REDEMPTION = "benefit_redemption"
METHOD_QR = "qr_scan"
METHOD_MANUAL = "manual"
SUCCESS = "success"
REJECTED = "rejected"
PENDING = "pending"
CONFIRMED = "confirmed"
CANCELLED = "cancelled"
QUALIFYING_STATUSES = (SUCCESS, PENDING, CONFIRMED)
MANUAL_TYPES = {VISIT, REDEMPTION}
MANUAL_STATUSES = {PENDING, CONFIRMED}
EDITABLE_STATUSES = {PENDING, CONFIRMED, CANCELLED}
ACTIVITY_TYPES = {SCAN, VISIT, REDEMPTION}
METHODS = {METHOD_QR, METHOD_MANUAL}
STATUSES = {SUCCESS, REJECTED, PENDING, CONFIRMED, CANCELLED}
MATCHES = {"alumni", "scans", "visits", "redemptions"}
_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")
TYPE_LABELS = {
    SCAN: "QR Scan",
    VISIT: "Partner Visit",
    REDEMPTION: "Benefit Redemption",
}
METHOD_LABELS = {METHOD_QR: "QR Scan", METHOD_MANUAL: "Manual Entry"}
STATUS_LABELS = {
    SUCCESS: "Successful",
    REJECTED: "Unsuccessful",
    PENDING: "Pending",
    CONFIRMED: "Confirmed",
    CANCELLED: "Cancelled",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _join_name(*parts: object) -> str:
    return " ".join(str(part).strip() for part in parts if str(part or "").strip())


def _person_name(account: Account | None) -> str:
    if account is None:
        return ""
    profile = account.profile
    if profile is not None:
        name = _join_name(profile.first_name, profile.middle_name, profile.last_name)
        if name:
            return name
    record = account.university_record
    if record is not None:
        name = _join_name(record.first_name, record.middle_name, record.last_name)
        if name:
            return name
    return _join_name(account.first_name, account.last_name)


def _student_number(account: Account | None) -> str:
    if account is None:
        return ""
    record = account.university_record
    if record is not None and str(record.student_id or "").strip():
        return str(record.student_id).strip()
    return str(account.linked_student_id or "").strip()


def _perk_usable(perk: AlumniPerk, today: date | None = None) -> bool:
    today = today or datetime.now(MANILA).date()
    if not perk.active:
        return False
    if perk.valid_from and perk.valid_from > today:
        return False
    if not perk.valid_until_further_notice and perk.valid_to and perk.valid_to < today:
        return False
    return True


def _partner_groups(db: Session) -> dict[str, list[AlumniPerk]]:
    grouped: dict[str, list[AlumniPerk]] = {}
    rows = db.query(AlumniPerk).order_by(AlumniPerk.partner.asc(), AlumniPerk.name.asc()).all()
    for perk in rows:
        name = (perk.partner or "").strip()
        if not name:
            continue
        grouped.setdefault(name, []).append(perk)
    return grouped


def partner_catalog(db: Session) -> list[dict]:
    today = datetime.now(MANILA).date()
    historical = {
        (name or "").strip()
        for (name,) in db.query(PartnerActivity.partner_name).distinct().all()
        if (name or "").strip()
    }
    grouped = _partner_groups(db)
    names = sorted(set(grouped) | historical, key=str.lower)
    items = []
    for name in names:
        perks = grouped.get(name, [])
        active = any(_perk_usable(perk, today) for perk in perks)
        items.append(
            {
                "name": name,
                "active": active,
                "perks": [
                    {
                        "id": perk.id,
                        "name": perk.name,
                        "discount": perk.discount or "",
                        "active": bool(perk.active),
                        "usable": _perk_usable(perk, today),
                        "requires_active_card": bool(perk.requires_active_card),
                    }
                    for perk in perks
                ],
            }
        )
    return items


def _require_active_partner(db: Session, partner: str) -> str:
    name = (partner or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Select a partner establishment.")
    grouped = _partner_groups(db)
    perks = grouped.get(name)
    if perks is None:
        raise HTTPException(status_code=400, detail="Select a partner establishment from the existing perk records.")
    if not any(_perk_usable(perk) for perk in perks):
        raise HTTPException(status_code=400, detail="This partner has no active benefit that can be used for a new activity.")
    return name


def _benefit_label(perk: AlumniPerk) -> str:
    discount = (perk.discount or "").strip()
    if discount:
        return f"{perk.name} — {discount}"
    return perk.name


def _usable_perk(db: Session, perk_id: int | None, partner: str) -> AlumniPerk | None:
    if perk_id is None:
        return None
    perk = db.get(AlumniPerk, perk_id)
    if perk is None or (perk.partner or "").strip() != partner:
        raise HTTPException(status_code=400, detail="Select a benefit offered by this partner.")
    if not _perk_usable(perk):
        raise HTTPException(status_code=400, detail="This benefit is inactive or outside its validity dates.")
    return perk


def _active_alumni(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None or account.role != "Alumni" or account.status != "Active":
        raise HTTPException(status_code=400, detail="Select an active alumni account.")
    return account


def _idempotency_key(value: str) -> str:
    key = (value or "").strip()
    if not _KEY_RE.fullmatch(key):
        raise HTTPException(status_code=400, detail="Enter an idempotency key so a retry is not recorded twice.")
    return key


def _existing_key(db: Session, key: str) -> PartnerActivity | None:
    return db.query(PartnerActivity).filter(PartnerActivity.idempotency_key == key).one_or_none()


def extract_qr_token(payload: str) -> str:
    text = unquote((payload or "").strip())
    marker = "/verify/qr/"
    if marker in text:
        text = text.split(marker, 1)[1]
        text = text.split("?", 1)[0].split("#", 1)[0].strip().strip("/")
    return text.strip()


def _fingerprint(token: str) -> str:
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


def _log(db: Session, admin_id: int, action: str, activity_id: int, old: dict | None, new: dict | None) -> None:
    db.add(
        AdminLog(
            admin_id=admin_id,
            action_type=action,
            target_id=str(activity_id),
            old_value=old,
            new_value=new,
        )
    )


def _snapshot(row: PartnerActivity) -> dict:
    return {
        "activity_type": row.activity_type,
        "recording_method": row.recording_method,
        "status": row.status,
        "partner_name": row.partner_name,
        "perk_id": row.perk_id,
        "benefit_label": row.benefit_label,
        "activity_at": row.activity_at.isoformat() if row.activity_at else None,
        "notes": row.notes or "",
        "alumni_account_id": row.alumni_account_id,
        "related_activity_id": row.related_activity_id,
    }


def _load_account(db: Session, account_id: int | None) -> Account | None:
    if account_id is None:
        return None
    return (
        db.query(Account)
        .options(joinedload(Account.profile), joinedload(Account.university_record))
        .filter(Account.id == account_id)
        .one_or_none()
    )


def serialize_activity(row: PartnerActivity, db: Session, *, include_audit: bool = False) -> dict:
    alumni = row.alumni or _load_account(db, row.alumni_account_id)
    recorder = row.recorded_by or _load_account(db, row.recorded_by_id)
    related = None
    if row.related_activity_id:
        linked = row.related_activity or db.get(PartnerActivity, row.related_activity_id)
        if linked is not None:
            related = {
                "id": linked.id,
                "activity_type": linked.activity_type,
                "activity_type_label": TYPE_LABELS.get(linked.activity_type, linked.activity_type),
                "status": linked.status,
                "status_label": STATUS_LABELS.get(linked.status, linked.status),
                "activity_at": linked.activity_at,
            }
    payload = {
        "id": row.id,
        "alumni_account_id": row.alumni_account_id,
        "alumni_name": _person_name(alumni),
        "student_number": _student_number(alumni),
        "email": alumni.personal_email if alumni is not None else "",
        "partner": row.partner_name,
        "activity_type": row.activity_type,
        "activity_type_label": TYPE_LABELS.get(row.activity_type, row.activity_type),
        "recording_method": row.recording_method,
        "recording_method_label": METHOD_LABELS.get(row.recording_method, row.recording_method),
        "status": row.status,
        "status_label": STATUS_LABELS.get(row.status, row.status),
        "activity_at": row.activity_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "benefit_label": row.benefit_label or "",
        "perk_id": row.perk_id,
        "notes": row.notes or "",
        "reference_code": row.reference_code or "",
        "outcome_detail": row.outcome_detail or "",
        "recorded_by_id": row.recorded_by_id,
        "recorded_by": _person_name(recorder) or (recorder.personal_email if recorder is not None else ""),
        "related_activity": related,
        "replayed": False,
    }
    if include_audit:
        logs = (
            db.query(AdminLog)
            .filter(AdminLog.target_id == str(row.id), AdminLog.action_type.like("partner_activity.%"))
            .order_by(AdminLog.created_at.asc(), AdminLog.id.asc())
            .all()
        )
        payload["audit"] = [
            {
                "id": entry.id,
                "action": entry.action_type,
                "created_at": entry.created_at,
                "admin_id": entry.admin_id,
                "old_value": entry.old_value,
                "new_value": entry.new_value,
            }
            for entry in logs
        ]
    return payload


def _parse_day(value: str, label: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Use a YYYY-MM-DD {label}.") from exc


def _apply_scope(query, db: Session, *, date_from: str, date_to: str, partner: str, search: str):
    start_day = _parse_day(date_from, "start date")
    end_day = _parse_day(date_to, "end date")
    if start_day and end_day and start_day > end_day:
        raise HTTPException(status_code=400, detail="The start date must be on or before the end date.")
    if start_day:
        start = datetime.combine(start_day, time.min, tzinfo=MANILA)
        query = query.filter(PartnerActivity.activity_at >= start)
    if end_day:
        end = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=MANILA)
        query = query.filter(PartnerActivity.activity_at < end)
    partner_name = (partner or "").strip()
    if partner_name:
        query = query.filter(PartnerActivity.partner_name == partner_name)
    terms = [part for part in (search or "").split() if part.strip()]
    if terms:
        query = (
            query.outerjoin(Account, Account.id == PartnerActivity.alumni_account_id)
            .outerjoin(AlumniProfile, AlumniProfile.account_id == Account.id)
            .outerjoin(UniversityRecord, UniversityRecord.student_id == Account.linked_student_id)
        )
        for term in terms:
            like = f"%{term}%"
            query = query.filter(
                or_(
                    Account.personal_email.ilike(like),
                    Account.linked_student_id.ilike(like),
                    Account.first_name.ilike(like),
                    Account.last_name.ilike(like),
                    AlumniProfile.first_name.ilike(like),
                    AlumniProfile.middle_name.ilike(like),
                    AlumniProfile.last_name.ilike(like),
                    UniversityRecord.first_name.ilike(like),
                    UniversityRecord.middle_name.ilike(like),
                    UniversityRecord.last_name.ilike(like),
                    UniversityRecord.student_id.ilike(like),
                    PartnerActivity.partner_name.ilike(like),
                    PartnerActivity.benefit_label.ilike(like),
                )
            )
    return query


def _apply_match(query, match: str):
    if not match:
        return query
    if match not in MATCHES:
        raise HTTPException(status_code=400, detail="Unknown activity view.")
    if match == "alumni":
        return query.filter(
            PartnerActivity.alumni_account_id.isnot(None),
            PartnerActivity.status.in_(QUALIFYING_STATUSES),
        )
    if match == "scans":
        return query.filter(PartnerActivity.activity_type == SCAN)
    if match == "visits":
        return query.filter(PartnerActivity.activity_type == VISIT, PartnerActivity.status != CANCELLED)
    return query.filter(PartnerActivity.activity_type == REDEMPTION, PartnerActivity.status == CONFIRMED)


def _apply_table_filters(query, *, activity_type: str, method: str, status: str, match: str, perk_id: int | None = None):
    if perk_id:
        query = query.filter(PartnerActivity.perk_id == perk_id)
    if match:
        return _apply_match(query, match)
    if activity_type:
        if activity_type not in ACTIVITY_TYPES:
            raise HTTPException(status_code=400, detail="Unknown activity type.")
        query = query.filter(PartnerActivity.activity_type == activity_type)
    if method:
        if method not in METHODS:
            raise HTTPException(status_code=400, detail="Unknown recording method.")
        query = query.filter(PartnerActivity.recording_method == method)
    if status:
        if status not in STATUSES:
            raise HTTPException(status_code=400, detail="Unknown verification status.")
        query = query.filter(PartnerActivity.status == status)
    return query


def _ordered(query, sort_by: str, sort_dir: str):
    direction = "asc" if (sort_dir or "").lower() == "asc" else "desc"
    column = {
        "activity_at": PartnerActivity.activity_at,
        "partner": PartnerActivity.partner_name,
        "type": PartnerActivity.activity_type,
        "status": PartnerActivity.status,
    }.get(sort_by or "activity_at", PartnerActivity.activity_at)
    ordering = column.asc() if direction == "asc" else column.desc()
    return query.order_by(ordering, PartnerActivity.id.desc())


def _with_people(query):
    return query.options(
        joinedload(PartnerActivity.alumni).joinedload(Account.profile),
        joinedload(PartnerActivity.alumni).joinedload(Account.university_record),
        joinedload(PartnerActivity.recorded_by),
        joinedload(PartnerActivity.related_activity),
    )


def summary(db: Session, *, date_from: str = "", date_to: str = "", partner: str = "", search: str = "") -> dict:
    scope = _apply_scope(db.query(PartnerActivity), db, date_from=date_from, date_to=date_to, partner=partner, search=search)
    qualifying = scope.filter(
        PartnerActivity.alumni_account_id.isnot(None),
        PartnerActivity.status.in_(QUALIFYING_STATUSES),
    )
    unique_alumni = qualifying.with_entities(PartnerActivity.alumni_account_id).distinct().count()
    scans = scope.filter(PartnerActivity.activity_type == SCAN)
    return {
        "unique_alumni": unique_alumni,
        "qr_scans": scans.count(),
        "qr_scans_successful": scans.filter(PartnerActivity.status == SUCCESS).count(),
        "qr_scans_unsuccessful": scans.filter(PartnerActivity.status == REJECTED).count(),
        "partner_visits": scope.filter(PartnerActivity.activity_type == VISIT, PartnerActivity.status != CANCELLED).count(),
        "confirmed_redemptions": scope.filter(
            PartnerActivity.activity_type == REDEMPTION,
            PartnerActivity.status == CONFIRMED,
        ).count(),
    }


def list_activities(
    db: Session,
    *,
    date_from: str = "",
    date_to: str = "",
    partner: str = "",
    search: str = "",
    activity_type: str = "",
    method: str = "",
    status: str = "",
    match: str = "",
    perk_id: int | None = None,
    page: int = 1,
    page_size: int = 12,
    sort_by: str = "activity_at",
    sort_dir: str = "desc",
) -> dict:
    page = max(1, page)
    page_size = min(50, max(5, page_size))
    query = _apply_scope(db.query(PartnerActivity), db, date_from=date_from, date_to=date_to, partner=partner, search=search)
    query = _apply_table_filters(
        query,
        activity_type=activity_type,
        method=method,
        status=status,
        match=match,
        perk_id=perk_id,
    )
    total = query.order_by(None).count()
    rows = _with_people(_ordered(query, sort_by, sort_dir)).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [serialize_activity(row, db) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def activity_detail(db: Session, activity_id: int) -> dict:
    row = _with_people(db.query(PartnerActivity).filter(PartnerActivity.id == activity_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Activity not found.")
    return serialize_activity(row, db, include_audit=True)


def search_alumni(db: Session, search: str) -> list[dict]:
    text = (search or "").strip()
    if len(text) < 2:
        return []
    query = (
        db.query(Account)
        .options(joinedload(Account.profile), joinedload(Account.university_record))
        .outerjoin(AlumniProfile, AlumniProfile.account_id == Account.id)
        .outerjoin(UniversityRecord, UniversityRecord.student_id == Account.linked_student_id)
        .filter(Account.role == "Alumni", Account.status == "Active")
    )
    for term in text.split():
        like = f"%{term}%"
        query = query.filter(
            or_(
                Account.personal_email.ilike(like),
                Account.linked_student_id.ilike(like),
                AlumniProfile.first_name.ilike(like),
                AlumniProfile.middle_name.ilike(like),
                AlumniProfile.last_name.ilike(like),
                UniversityRecord.first_name.ilike(like),
                UniversityRecord.middle_name.ilike(like),
                UniversityRecord.last_name.ilike(like),
                UniversityRecord.student_id.ilike(like),
            )
        )
    rows = query.order_by(Account.personal_email.asc()).limit(8).all()
    return [
        {
            "id": row.id,
            "name": _person_name(row) or row.personal_email,
            "student_number": _student_number(row),
            "email": row.personal_email,
        }
        for row in rows
    ]


def _store(db: Session, row: PartnerActivity, admin: Account) -> PartnerActivity:
    db.add(row)
    db.flush()
    _log(db, admin.id, "partner_activity.create", row.id, None, _snapshot(row))
    db.commit()
    db.refresh(row)
    return row


def record_scan(db: Session, admin: Account, *, partner: str, payload: str, idempotency_key: str, notes: str = "") -> tuple[PartnerActivity, bool]:
    key = _idempotency_key(idempotency_key)
    existing = _existing_key(db, key)
    if existing is not None:
        if existing.recording_method != METHOD_QR:
            raise HTTPException(status_code=409, detail="This idempotency key was already used for a different activity.")
        return existing, True
    partner_name = _require_active_partner(db, partner)
    token = extract_qr_token(payload)
    account_id = account_id_from_token(token) if token else None
    account = db.get(Account, account_id) if account_id else None
    status = SUCCESS
    detail = "The partner scan was verified."
    linked_id = None
    if account is None or account.role != "Alumni":
        status = REJECTED
        detail = "This QR code could not be verified."
        account = None
    elif account.status != "Active":
        status = REJECTED
        detail = "This alumni account is not active."
        linked_id = account.id
    else:
        linked_id = account.id
    row = PartnerActivity(
        alumni_account_id=linked_id,
        activity_type=SCAN,
        recording_method=METHOD_QR,
        status=status,
        partner_name=partner_name,
        activity_at=_now(),
        notes=(notes or "").strip(),
        outcome_detail=detail,
        token_fingerprint=_fingerprint(token),
        idempotency_key=key,
        recorded_by_id=admin.id,
        created_at=_now(),
        updated_at=_now(),
    )
    return _store(db, row, admin), False


def record_manual(
    db: Session,
    admin: Account,
    *,
    alumni_account_id: int,
    partner: str,
    activity_type: str,
    activity_at: datetime,
    status: str,
    perk_id: int | None,
    notes: str,
    reference_code: str,
    idempotency_key: str,
    related_activity_id: int | None,
) -> tuple[PartnerActivity, bool]:
    key = _idempotency_key(idempotency_key)
    existing = _existing_key(db, key)
    if existing is not None:
        if existing.recording_method != METHOD_MANUAL:
            raise HTTPException(status_code=409, detail="This idempotency key was already used for a different activity.")
        return existing, True
    if activity_type not in MANUAL_TYPES:
        raise HTTPException(status_code=400, detail="Choose a partner visit or a benefit redemption. QR scans are recorded from the scanner.")
    if status not in MANUAL_STATUSES:
        raise HTTPException(status_code=400, detail="Choose Pending or Confirmed. A manual entry is not a QR scan.")
    if activity_at is None:
        raise HTTPException(status_code=400, detail="Enter the activity date and time.")
    moment = _aware(activity_at)
    if moment > _now() + timedelta(minutes=2):
        raise HTTPException(status_code=400, detail="The activity date cannot be in the future.")
    if moment.year < 1990:
        raise HTTPException(status_code=400, detail="Enter an activity date in 1990 or later.")
    partner_name = _require_active_partner(db, partner)
    alumni = _active_alumni(db, alumni_account_id)
    perk = _usable_perk(db, perk_id, partner_name)
    if activity_type == REDEMPTION and perk is None:
        raise HTTPException(status_code=400, detail="Select the benefit or discount that was redeemed.")
    related_id = None
    if related_activity_id:
        linked = db.get(PartnerActivity, related_activity_id)
        if linked is None or linked.alumni_account_id != alumni.id:
            raise HTTPException(status_code=400, detail="The related activity must belong to this alumnus.")
        related_id = linked.id
    row = PartnerActivity(
        alumni_account_id=alumni.id,
        activity_type=activity_type,
        recording_method=METHOD_MANUAL,
        status=status,
        partner_name=partner_name,
        perk_id=perk.id if perk is not None else None,
        benefit_label=_benefit_label(perk) if perk is not None else "",
        activity_at=moment,
        notes=(notes or "").strip(),
        reference_code=(reference_code or "").strip()[:80],
        outcome_detail="Recorded manually by an administrator.",
        idempotency_key=key,
        related_activity_id=related_id,
        recorded_by_id=admin.id,
        created_at=_now(),
        updated_at=_now(),
    )
    return _store(db, row, admin), False


def update_activity(db: Session, admin: Account, activity_id: int, *, status: str | None, notes: str | None) -> PartnerActivity:
    row = db.get(PartnerActivity, activity_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Activity not found.")
    before = _snapshot(row)
    if status:
        if row.activity_type == SCAN and status != row.status:
            raise HTTPException(status_code=400, detail="A QR scan outcome cannot be changed into a visit or redemption.")
        if row.activity_type != SCAN and status not in EDITABLE_STATUSES:
            raise HTTPException(status_code=400, detail="Choose Pending, Confirmed, or Cancelled.")
        if row.recording_method == METHOD_MANUAL and status in {SUCCESS, REJECTED}:
            raise HTTPException(status_code=400, detail="A manual entry cannot be marked as a QR scan outcome.")
        row.status = status
        if status == CONFIRMED:
            row.outcome_detail = "Confirmed by an administrator."
        elif status == CANCELLED:
            row.outcome_detail = "Cancelled by an administrator."
        elif status == PENDING:
            row.outcome_detail = "Marked pending by an administrator."
    if notes is not None:
        row.notes = notes.strip()
    row.updated_at = _now()
    _log(db, admin.id, "partner_activity.update", row.id, before, _snapshot(row))
    db.commit()
    db.refresh(row)
    return row


def export_rows(db: Session, **filters) -> list[PartnerActivity]:
    query = _apply_scope(
        db.query(PartnerActivity),
        db,
        date_from=filters.get("date_from", ""),
        date_to=filters.get("date_to", ""),
        partner=filters.get("partner", ""),
        search=filters.get("search", ""),
    )
    query = _apply_table_filters(
        query,
        activity_type=filters.get("activity_type", ""),
        method=filters.get("method", ""),
        status=filters.get("status", ""),
        match=filters.get("match", ""),
        perk_id=filters.get("perk_id"),
    )
    return _with_people(_ordered(query, filters.get("sort_by", "activity_at"), filters.get("sort_dir", "desc"))).limit(5000).all()

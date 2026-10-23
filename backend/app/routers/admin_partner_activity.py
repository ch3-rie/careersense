import csv
import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Account
from app.services.partner_activity import (
    activity_detail,
    export_rows,
    list_activities,
    partner_catalog,
    record_manual,
    record_scan,
    search_alumni,
    serialize_activity,
    summary,
    update_activity,
)

router = APIRouter(prefix="/api/admin/partner-activity", tags=["admin-partner-activity"])
MANILA = ZoneInfo("Asia/Manila")


def _manila(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(MANILA)


class ScanIn(BaseModel):
    partner: str = ""
    payload: str = ""
    idempotency_key: str = ""
    notes: str = ""


class ManualIn(BaseModel):
    alumni_account_id: int
    partner: str = ""
    activity_type: str = ""
    activity_at: datetime
    status: str = "pending"
    perk_id: int | None = None
    notes: str = ""
    reference_code: str = Field(default="", max_length=80)
    idempotency_key: str = ""
    related_activity_id: int | None = None


class ActivityUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


def _filters(
    date_from: str = "",
    date_to: str = "",
    partner: str = "",
    q: str = "",
    activity_type: str = "",
    method: str = "",
    status: str = "",
    match: str = "",
    sort_by: str = "activity_at",
    sort_dir: str = "desc",
    perk_id: int | None = None,
) -> dict:
    return {
        "date_from": date_from,
        "date_to": date_to,
        "partner": partner,
        "search": q,
        "activity_type": activity_type,
        "method": method,
        "status": status,
        "match": match,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "perk_id": perk_id or None,
    }


@router.get("/summary")
def activity_summary(
    date_from: str = "",
    date_to: str = "",
    partner: str = "",
    q: str = "",
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return summary(db, date_from=date_from, date_to=date_to, partner=partner, search=q)


@router.get("/partners")
def partners(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    return {"items": partner_catalog(db)}


@router.get("/alumni")
def alumni(q: str = "", admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    return {"items": search_alumni(db, q)}


@router.get("/export")
def export_activities(
    date_from: str = "",
    date_to: str = "",
    partner: str = "",
    q: str = "",
    activity_type: str = "",
    method: str = "",
    status: str = "",
    match: str = "",
    perk_id: int | None = None,
    sort_by: str = "activity_at",
    sort_dir: str = "desc",
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = export_rows(
        db,
        **_filters(date_from, date_to, partner, q, activity_type, method, status, match, sort_by, sort_dir, perk_id),
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Alumni name",
            "Student number",
            "Email",
            "Partner establishment",
            "Activity type",
            "Recording method",
            "Activity date",
            "Activity time",
            "Status",
            "Benefit or discount",
            "Notes",
            "Reference",
            "Recorded by",
            "Activity timestamp",
            "Recorded at",
        ]
    )
    for row in rows:
        item = serialize_activity(row, db)
        moment = _manila(item["activity_at"])
        created = _manila(item["created_at"])
        writer.writerow(
            [
                item["alumni_name"],
                item["student_number"],
                item["email"],
                item["partner"],
                item["activity_type_label"],
                item["recording_method_label"],
                moment.strftime("%Y-%m-%d") if moment else "",
                moment.strftime("%H:%M") if moment else "",
                item["status_label"],
                item["benefit_label"],
                item["notes"],
                item["reference_code"],
                item["recorded_by"],
                moment.isoformat() if moment else "",
                created.isoformat() if created else "",
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=partner-activity.csv"},
    )


@router.get("")
def activities(
    date_from: str = "",
    date_to: str = "",
    partner: str = "",
    q: str = "",
    activity_type: str = "",
    method: str = "",
    status: str = "",
    match: str = "",
    perk_id: int | None = None,
    page: int = 1,
    page_size: int = 12,
    sort_by: str = "activity_at",
    sort_dir: str = "desc",
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_activities(
        db,
        page=page,
        page_size=page_size,
        **_filters(date_from, date_to, partner, q, activity_type, method, status, match, sort_by, sort_dir, perk_id),
    )


@router.get("/{activity_id}")
def one_activity(activity_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    return activity_detail(db, activity_id)


@router.post("/scans")
def create_scan(payload: ScanIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    if not (payload.payload or "").strip():
        raise HTTPException(status_code=400, detail="Paste the alumni QR code or its verification link.")
    row, replayed = record_scan(
        db,
        admin,
        partner=payload.partner,
        payload=payload.payload,
        idempotency_key=payload.idempotency_key,
        notes=payload.notes,
    )
    body = serialize_activity(row, db)
    body["replayed"] = replayed
    return body


@router.post("")
def create_manual(payload: ManualIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row, replayed = record_manual(
        db,
        admin,
        alumni_account_id=payload.alumni_account_id,
        partner=payload.partner,
        activity_type=payload.activity_type,
        activity_at=payload.activity_at,
        status=payload.status,
        perk_id=payload.perk_id,
        notes=payload.notes,
        reference_code=payload.reference_code,
        idempotency_key=payload.idempotency_key,
        related_activity_id=payload.related_activity_id,
    )
    body = serialize_activity(row, db)
    body["replayed"] = replayed
    return body


@router.patch("/{activity_id}")
def patch_activity(
    activity_id: int,
    payload: ActivityUpdate,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if payload.status is None and payload.notes is None:
        raise HTTPException(status_code=400, detail="There is nothing to update.")
    row = update_activity(db, admin, activity_id, status=payload.status, notes=payload.notes)
    return serialize_activity(row, db, include_audit=True)

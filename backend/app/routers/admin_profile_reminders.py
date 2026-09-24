from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Account
from app.schemas import ProfileReminderRunIn, ProfileReminderSettingsIn
from app.services.profile_reminders import (
    list_runs,
    preview_recipients,
    run_reminders,
    save_settings,
    serialize_run_detail,
    serialize_settings,
)

router = APIRouter(prefix="/api/admin/profile-reminders", tags=["admin-profile-reminders"])


@router.get("")
def get_settings(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    payload = serialize_settings(db)
    db.commit()
    return payload


@router.put("")
def update_settings(
    payload: ProfileReminderSettingsIn,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return save_settings(db, admin, payload)


@router.get("/preview")
def preview(
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    payload = preview_recipients(db)
    db.commit()
    return payload


@router.get("/runs")
def runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=5, le=50),
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_runs(db, page=page, page_size=page_size)


@router.get("/runs/{run_id}")
def run_detail(
    run_id: int,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return serialize_run_detail(db, run_id)


@router.post("/run")
def run_now(
    payload: ProfileReminderRunIn = Body(default=ProfileReminderRunIn()),
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return run_reminders(db, triggered_by="admin", admin=admin, force=payload.force)

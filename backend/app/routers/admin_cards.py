import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import require_admin
from app.models import Account, AdminLog, AlumniCard, AlumniProfile
from app.schemas import AppointmentSlotIn, CardStatusIn
from app.services.alumni_hub import (
    CARD_META,
    CARD_TRANSITIONS,
    canonical_card_status,
    serialize_card,
    transition_alumni_card_status,
)
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


def _serialize_item(account: Account) -> dict:
    card = serialize_card(account.alumni_card)
    application = card.get("application") or {}
    return {
        "id": account.id,
        "email": account.personal_email,
        "name": _account_name(account),
        "student_id": account.linked_student_id,
        "degree": account.profile.degree if account.profile else "",
        "status": card["status"],
        "label": card["label"],
        "submitted_at": card.get("submitted_at"),
        "membership_type": application.get("membership_type") or card.get("membership_type") or "",
        "card_number": card.get("card_number") or "",
        "next_statuses": list(CARD_TRANSITIONS.get(card["status"], ())),
    }


@router.get("")
def list_cards(
    page: int = 1,
    page_size: int = 10,
    q: str = "",
    status: str = "",
    sort_by: str = "submitted",
    sort_dir: str = "desc",
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    page = max(1, page)
    page_size = min(50, max(5, page_size))
    query = (
        db.query(Account)
        .join(AlumniCard, AlumniCard.account_id == Account.id)
        .outerjoin(AlumniProfile, AlumniProfile.account_id == Account.id)
        .options(joinedload(Account.profile), joinedload(Account.alumni_card))
        .filter(Account.role == "Alumni")
    )
    wanted = (status or "").strip()
    if wanted:
        if wanted not in CARD_META:
            raise HTTPException(status_code=400, detail="Unsupported alumni card status filter.")
        query = query.filter(AlumniCard.status == wanted)
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            or_(
                Account.personal_email.ilike(like),
                Account.linked_student_id.ilike(like),
                AlumniProfile.first_name.ilike(like),
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
        .options(joinedload(Account.profile), joinedload(Account.alumni_card))
        .filter(Account.id == account_id, Account.role == "Alumni")
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Alumni account not found.")
    card = serialize_card(user.alumni_card)
    return {
        "account": {
            "id": user.id,
            "email": user.personal_email,
            "name": _account_name(user),
            "student_id": user.linked_student_id,
            "status": user.status,
            "degree": user.profile.degree if user.profile else "",
            "year_graduated": user.profile.year_graduated if user.profile else "",
            "phone": user.profile.phone if user.profile else "",
            "city": user.profile.city if user.profile else "",
        },
        "card": card,
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
        .options(joinedload(Account.profile), joinedload(Account.alumni_card))
        .filter(Account.id == account_id, Account.role == "Alumni")
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Alumni account not found.")
    if user.status != "Active":
        raise HTTPException(status_code=400, detail="Only Active alumni can have an alumni card processed.")
    old = canonical_card_status(user.alumni_card)
    card, already = transition_alumni_card_status(
        db,
        user,
        payload.status,
        pickup_location=payload.pickup_location,
        card_number=payload.card_number,
        note=payload.note,
    )
    if not already:
        _log(
            db,
            admin.id,
            "AAC_STATUS",
            user.id,
            {"status": old},
            {"status": canonical_card_status(card), "note": payload.note or ""},
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

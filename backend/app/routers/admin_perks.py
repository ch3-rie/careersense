from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Account, AdminLog, AlumniPerk, AlumniPerkRedemption
from app.schemas import PerkIn
from app.services.files import resolve_stored_file, save_perk_image, unlink_contained_file
from app.services.validation import sanitize_http_url


def perk_is_expired(valid_to: date | None, today: date | None = None) -> bool:
    if valid_to is None:
        return False
    today = today or date.today()
    return valid_to < today

router = APIRouter(prefix="/api/admin/perks", tags=["admin-perks"])


def _log(db: Session, admin_id: int, action: str, target_id, old=None, new=None) -> None:
    db.add(AdminLog(admin_id=admin_id, action_type=action, target_id=str(target_id or ""), old_value=old, new_value=new))


def serialize_admin_perk(perk: AlumniPerk) -> dict:
    today = date.today()
    expiring = bool(perk.active and perk.valid_to and today <= perk.valid_to <= today + timedelta(days=30))
    return {
        "id": perk.id,
        "name": perk.name,
        "partner": perk.partner or "",
        "category": perk.category or "",
        "description": perk.description or "",
        "discount": perk.discount or "",
        "how_to_claim": perk.how_to_claim or "",
        "eligibility": perk.eligibility or "",
        "contact": perk.contact or "",
        "website": sanitize_http_url(perk.website or ""),
        "valid_from": perk.valid_from.isoformat() if perk.valid_from else None,
        "valid_to": perk.valid_to.isoformat() if perk.valid_to else None,
        "requires_active_card": bool(perk.requires_active_card),
        "active": bool(perk.active),
        "status": "Active" if perk.active else "Inactive",
        "expired": perk_is_expired(perk.valid_to, today),
        "expiring_soon": expiring,
        "has_image": bool(perk.image_path),
        "image_url": f"/api/admin/perks/{perk.id}/image" if perk.image_path else None,
    }


def _apply(perk: AlumniPerk, payload: PerkIn) -> None:
    perk.name = payload.name.strip()
    perk.partner = (payload.partner or "").strip()
    perk.category = (payload.category or "").strip()
    perk.description = payload.description or ""
    perk.discount = (payload.discount or "").strip()
    perk.how_to_claim = payload.how_to_claim or ""
    perk.eligibility = payload.eligibility or ""
    perk.contact = (payload.contact or "").strip()
    perk.website = sanitize_http_url(payload.website or "", strict=True)
    perk.valid_from = payload.valid_from
    perk.valid_to = payload.valid_to
    perk.requires_active_card = payload.requires_active_card
    perk.active = payload.active


def _unique_name(db: Session, name: str, exclude_id: int | None = None) -> None:
    query = db.query(AlumniPerk).filter(AlumniPerk.name == name.strip())
    if exclude_id is not None:
        query = query.filter(AlumniPerk.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=400, detail="A perk with this name already exists.")


@router.get("")
def list_perks(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(AlumniPerk).order_by(AlumniPerk.name.asc()).all()
    items = [serialize_admin_perk(row) for row in rows]
    return {
        "items": items,
        "total": len(items),
        "active": sum(1 for row in items if row["active"]),
        "inactive": sum(1 for row in items if not row["active"]),
        "expiring_soon": sum(1 for row in items if row["expiring_soon"]),
        "categories": sorted({row["category"] for row in items if row["category"]}),
    }


@router.get("/{perk_id}")
def get_perk(perk_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    perk = db.get(AlumniPerk, perk_id)
    if not perk:
        raise HTTPException(status_code=404, detail="Perk not found.")
    return serialize_admin_perk(perk)


@router.post("")
def create_perk(payload: PerkIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Perk name is required.")
    _unique_name(db, payload.name)
    perk = AlumniPerk()
    _apply(perk, payload)
    db.add(perk)
    db.flush()
    _log(db, admin.id, "CREATE_PERK", perk.id, None, {"name": perk.name, "active": perk.active})
    db.commit()
    db.refresh(perk)
    return {"ok": True, "message": "Perk added successfully", "item": serialize_admin_perk(perk)}


@router.put("/{perk_id}")
def update_perk(perk_id: int, payload: PerkIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    perk = db.get(AlumniPerk, perk_id)
    if not perk:
        raise HTTPException(status_code=404, detail="Perk not found.")
    _unique_name(db, payload.name, exclude_id=perk.id)
    _apply(perk, payload)
    _log(db, admin.id, "UPDATE_PERK", perk.id, None, {"name": perk.name, "active": perk.active})
    db.commit()
    db.refresh(perk)
    return {"ok": True, "message": "Perk updated successfully", "item": serialize_admin_perk(perk)}


@router.post("/{perk_id}/toggle")
def toggle_perk(perk_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    perk = db.get(AlumniPerk, perk_id)
    if not perk:
        raise HTTPException(status_code=404, detail="Perk not found.")
    perk.active = not perk.active
    _log(db, admin.id, "TOGGLE_PERK", perk.id, None, {"active": perk.active})
    db.commit()
    db.refresh(perk)
    return {
        "ok": True,
        "message": "Perk activated" if perk.active else "Perk deactivated",
        "item": serialize_admin_perk(perk),
    }


@router.delete("/{perk_id}")
def delete_perk(perk_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    perk = db.get(AlumniPerk, perk_id)
    if not perk:
        raise HTTPException(status_code=404, detail="Perk not found.")
    db.query(AlumniPerkRedemption).filter(AlumniPerkRedemption.perk_id == perk.id).delete()
    if perk.image_path:
        unlink_contained_file(perk.image_path)
    _log(db, admin.id, "DELETE_PERK", perk.id, {"name": perk.name}, None)
    db.delete(perk)
    db.commit()
    return {"ok": True, "message": "Perk deleted"}


@router.post("/{perk_id}/image")
async def upload_perk_image(
    perk_id: int,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
    image: UploadFile = File(...),
):
    perk = db.get(AlumniPerk, perk_id)
    if not perk:
        raise HTTPException(status_code=404, detail="Perk not found.")
    data = await image.read()
    stored, mime = save_perk_image(perk.id, data)
    previous = perk.image_path
    perk.image_path = str(stored)
    perk.image_mime = mime
    db.commit()
    if previous and previous != str(stored):
        unlink_contained_file(previous)
    return {"ok": True, "message": "Image uploaded", "item": serialize_admin_perk(perk)}


@router.get("/{perk_id}/image")
def perk_image(perk_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    perk = db.get(AlumniPerk, perk_id)
    if not perk or not perk.image_path:
        raise HTTPException(status_code=404, detail="Image not found.")
    path = resolve_stored_file(perk.image_path, missing_detail="Image not found.")
    return FileResponse(path, media_type=perk.image_mime or "image/jpeg")

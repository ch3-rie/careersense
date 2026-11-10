from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Account, AdminLog, BadgeDefinition
from app.services.badge_admin import _counts, _now, create_badge, list_badges, remove_badge, serialize_definition, update_badge
from app.services.files import resolve_stored_file, save_badge_image, unlink_contained_file

router = APIRouter(prefix="/api/admin/badges", tags=["admin-badges"])


class BadgeWrite(BaseModel):
    name: str = ""
    description: str = ""
    locked_description: str = ""
    icon: str = "check"
    category: str = "recognition"
    criteria_type: str = ""
    active: bool = True


def _log(db: Session, admin_id: int, action: str, target_id, old=None, new=None) -> None:
    db.add(AdminLog(admin_id=admin_id, action_type=action, target_id=str(target_id or ""), old_value=old, new_value=new))


def _get(db: Session, badge_id: int) -> BadgeDefinition:
    row = db.get(BadgeDefinition, badge_id)
    if not row:
        raise HTTPException(status_code=404, detail="Badge not found.")
    return row


@router.get("")
def get_badges(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    payload = list_badges(db)
    db.commit()
    return payload


@router.post("")
def post_badge(payload: BadgeWrite, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = create_badge(db, payload.model_dump())
    _log(db, admin.id, "CREATE_BADGE", row.id, None, {"name": row.name, "key": row.key, "active": row.active})
    db.commit()
    db.refresh(row)
    earned = _counts(db).get(row.key, 0)
    return {"ok": True, "message": "Badge added.", "item": serialize_definition(row, earned)}


@router.put("/{badge_id}")
def put_badge(badge_id: int, payload: BadgeWrite, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = _get(db, badge_id)
    update_badge(db, row, payload.model_dump())
    _log(db, admin.id, "UPDATE_BADGE", row.id, None, {"name": row.name, "active": row.active})
    db.commit()
    db.refresh(row)
    earned = _counts(db).get(row.key, 0)
    return {"ok": True, "message": "Badge updated.", "item": serialize_definition(row, earned)}


@router.post("/{badge_id}/toggle")
def toggle_badge(badge_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = _get(db, badge_id)
    row.active = not row.active
    row.updated_at = _now()
    _log(db, admin.id, "TOGGLE_BADGE", row.id, None, {"active": row.active})
    db.commit()
    db.refresh(row)
    earned = _counts(db).get(row.key, 0)
    message = "Badge activated." if row.active else "Badge deactivated. Alumni who already earned it keep the badge."
    return {"ok": True, "message": message, "item": serialize_definition(row, earned)}


@router.delete("/{badge_id}")
def delete_badge(badge_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = _get(db, badge_id)
    name = row.name
    result = remove_badge(db, row)
    _log(
        db,
        admin.id,
        "DELETE_BADGE" if result["removed"] else "DEACTIVATE_BADGE",
        badge_id,
        {"name": name},
        {"removed": result["removed"], "deactivated": result["deactivated"]},
    )
    stored = result.pop("image_path", "")
    db.commit()
    if stored:
        unlink_contained_file(stored)
    return {"ok": True, **result}


@router.post("/{badge_id}/image")
async def upload_badge_image(
    badge_id: int,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
    image: UploadFile = File(...),
):
    row = _get(db, badge_id)
    data = await image.read()
    stored, mime = save_badge_image(row.id, data)
    previous = row.image_path
    row.image_path = str(stored)
    row.image_mime = mime
    row.updated_at = _now()
    _log(db, admin.id, "UPLOAD_BADGE_IMAGE", row.id, None, {"name": row.name})
    db.commit()
    if previous and previous != str(stored):
        unlink_contained_file(previous)
    db.refresh(row)
    earned = _counts(db).get(row.key, 0)
    return {"ok": True, "message": "Badge image uploaded.", "item": serialize_definition(row, earned)}


@router.delete("/{badge_id}/image")
def delete_badge_image(badge_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = _get(db, badge_id)
    previous = row.image_path
    row.image_path = ""
    row.image_mime = ""
    row.updated_at = _now()
    _log(db, admin.id, "REMOVE_BADGE_IMAGE", row.id, None, {"name": row.name})
    db.commit()
    if previous:
        unlink_contained_file(previous)
    db.refresh(row)
    earned = _counts(db).get(row.key, 0)
    return {"ok": True, "message": "Badge image removed. The icon is shown instead.", "item": serialize_definition(row, earned)}


@router.get("/{badge_id}/image")
def badge_image(badge_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(BadgeDefinition, badge_id)
    if not row or not row.image_path:
        raise HTTPException(status_code=404, detail="Image not found.")
    path = resolve_stored_file(row.image_path, missing_detail="Image not found.")
    return FileResponse(path, media_type=row.image_mime or "image/png")

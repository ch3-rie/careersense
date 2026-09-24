from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Account, AdminLog
from app.schemas import AdminUserCreateIn, AdminUserUpdateIn
from app.security import generate_temp_password, hash_password
from app.services.validation import normalize_email, validate_password_strength

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])

ADMIN_ROLES = ["Admin"]
ADMIN_STATUSES = ["Active", "Inactive"]


def _log(db: Session, admin_id: int, action: str, target_id, old=None, new=None) -> None:
    db.add(AdminLog(admin_id=admin_id, action_type=action, target_id=str(target_id or ""), old_value=old, new_value=new))


def serialize_admin_user(user: Account) -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "name": " ".join(part for part in [user.first_name, user.last_name] if part).strip() or user.personal_email,
        "email": user.personal_email,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "must_change_password": bool(user.must_change_password),
    }


def _active_admin_count(db: Session) -> int:
    return db.query(Account).filter(Account.role == "Admin", Account.status == "Active").count()


def _get_admin_account(db: Session, user_id: int) -> Account:
    user = db.get(Account, user_id)
    if not user or user.role != "Admin":
        raise HTTPException(status_code=404, detail="Administrator not found.")
    return user


@router.get("")
def list_admins(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Account).filter(Account.role == "Admin").order_by(Account.created_at.asc()).all()
    items = [serialize_admin_user(row) for row in rows]
    return {
        "items": items,
        "total": len(items),
        "active": sum(1 for row in items if row["status"] == "Active"),
        "inactive": sum(1 for row in items if row["status"] != "Active"),
        "roles": ADMIN_ROLES,
    }


@router.get("/{user_id}")
def get_admin(user_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    return serialize_admin_user(_get_admin_account(db, user_id))


@router.post("")
def create_admin(payload: AdminUserCreateIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Confirm that you want to create this administrator account.")
    if payload.role not in ADMIN_ROLES:
        raise HTTPException(status_code=400, detail="Unsupported role.")
    if payload.status not in ADMIN_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be Active or Inactive.")
    email = normalize_email(str(payload.email))
    if db.query(Account).filter(Account.personal_email == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    temp = generate_temp_password()
    validate_password_strength(temp)
    user = Account(
        personal_email=email,
        password_hash=hash_password(temp),
        role=payload.role,
        status=payload.status,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        is_verified=True,
        privacy_consent=True,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    _log(
        db,
        admin.id,
        "CREATE_ADMIN",
        user.id,
        None,
        {"email": email, "role": payload.role, "created_by": admin.personal_email},
    )
    db.commit()
    db.refresh(user)
    return {
        "ok": True,
        "message": "Administrator created successfully",
        "item": serialize_admin_user(user),
        "temporary_password": temp,
    }


@router.patch("/{user_id}")
def update_admin(
    user_id: int,
    payload: AdminUserUpdateIn,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_admin_account(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        email = normalize_email(str(data["email"]))
        existing = db.query(Account).filter(Account.personal_email == email, Account.id != user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="An account with this email already exists.")
        user.personal_email = email
    if "first_name" in data and data["first_name"] is not None:
        user.first_name = data["first_name"].strip()
    if "last_name" in data and data["last_name"] is not None:
        user.last_name = data["last_name"].strip()
    if "role" in data and data["role"] is not None:
        if data["role"] not in ADMIN_ROLES:
            raise HTTPException(status_code=400, detail="Unsupported role.")
        user.role = data["role"]
    if "status" in data and data["status"] is not None:
        _set_status(db, admin, user, data["status"])
    _log(db, admin.id, "UPDATE_ADMIN", user.id, None, data)
    db.commit()
    db.refresh(user)
    return {"ok": True, "message": "Administrator updated", "item": serialize_admin_user(user)}


@router.post("/{user_id}/deactivate")
def deactivate_admin(user_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    user = _get_admin_account(db, user_id)
    _set_status(db, admin, user, "Inactive")
    db.commit()
    db.refresh(user)
    return {"ok": True, "message": "Administrator deactivated", "item": serialize_admin_user(user)}


@router.post("/{user_id}/activate")
def activate_admin(user_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    user = _get_admin_account(db, user_id)
    _set_status(db, admin, user, "Active")
    db.commit()
    db.refresh(user)
    return {"ok": True, "message": "Administrator activated", "item": serialize_admin_user(user)}


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    user = _get_admin_account(db, user_id)
    temp = generate_temp_password()
    validate_password_strength(temp)
    user.password_hash = hash_password(temp)
    user.must_change_password = True
    user.password_changed_at = datetime.now(timezone.utc)
    user.token_version = int(user.token_version or 0) + 1
    _log(db, admin.id, "RESET_ADMIN_PASSWORD", user.id)
    db.commit()
    return {
        "ok": True,
        "message": "Temporary password created. Share it securely; it will not be shown again.",
        "temporary_password": temp,
        "item": serialize_admin_user(user),
    }


def _set_status(db: Session, actor: Account, user: Account, status: str) -> None:
    if status not in ADMIN_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be Active or Inactive.")
    if status == "Inactive":
        if user.id == actor.id:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
        if user.status == "Active" and _active_admin_count(db) <= 1:
            raise HTTPException(status_code=400, detail="The last active administrator cannot be deactivated.")
    user.status = status
    _log(db, actor.id, "SET_ADMIN_STATUS", user.id, None, {"status": status})

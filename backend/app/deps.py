from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account
from app.security import require_access_payload

bearer = HTTPBearer(auto_error=False)


def _aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        from datetime import timezone

        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> Account:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue.")
    payload = require_access_payload(creds.credentials)
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue.")
    user = db.get(Account, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists.")

    current_ver = int(user.token_version or 0)
    token_ver = payload.get("ver")
    if token_ver is None:
        if current_ver != 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please sign in again.",
            )
    elif int(token_ver) != current_ver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        )

    changed = _aware(user.password_changed_at)
    if changed is not None and token_ver is None:
        iat = payload.get("iat")
        if not iat:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please sign in again.",
            )
        from datetime import datetime, timezone

        issued = datetime.fromtimestamp(int(iat), tz=timezone.utc)
        if issued.timestamp() + 1 < changed.timestamp():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please sign in again.",
            )
    return user


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> Optional[Account]:
    if creds is None:
        return None
    try:
        return get_current_user(creds, db)
    except HTTPException:
        return None


def require_alumni(user: Account = Depends(get_current_user)) -> Account:
    if user.role != "Alumni":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Alumni access required.")
    return user


def require_pending_or_active_alumni(user: Account = Depends(require_alumni)) -> Account:
    if user.status not in {"Pending", "Active"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account cannot access alumni records.",
        )
    return user


def require_active_alumni(user: Account = Depends(require_alumni)) -> Account:
    if user.status != "Active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account must be approved before accessing the alumni portal.",
        )
    return user


def require_admin(user: Account = Depends(get_current_user)) -> Account:
    if user.role != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required.")
    if user.status != "Active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This administrator account is inactive.")
    return user

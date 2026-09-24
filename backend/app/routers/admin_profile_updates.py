from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Account
from app.schemas import ProfileUpdateRequestIn
from app.services.profile_updates import (
    composer_defaults,
    create_request,
    get_request,
    list_requests,
    search_alumni,
)

router = APIRouter(prefix="/api/admin/profile-update-requests", tags=["admin-profile-updates"])


@router.get("/options")
def options(admin: Account = Depends(require_admin)):
    return composer_defaults()


@router.get("/alumni")
def alumni_directory(
    q: str = "",
    year: str = "",
    degree: str = "",
    completion: str = "",
    page: int = 1,
    page_size: int = 10,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return search_alumni(
        db,
        q=q,
        year=year,
        degree=degree,
        completion=completion,
        page=page,
        page_size=page_size,
    )


@router.get("")
def index(
    page: int = 1,
    page_size: int = 10,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_requests(db, page=page, page_size=page_size)


@router.post("")
def create(
    payload: ProfileUpdateRequestIn,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return create_request(db, admin, payload)


@router.get("/{request_id}")
def detail(
    request_id: int,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_request(db, request_id)

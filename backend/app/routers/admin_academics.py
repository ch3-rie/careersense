"""Administrator maintenance for the shared college and course catalog."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Account
from app.services.academic_catalog import (
    CatalogError,
    create_college,
    create_course,
    delete_college,
    delete_course,
    list_academics,
    update_college,
    update_course,
)

router = APIRouter(prefix="/api/admin/academics", tags=["admin-academics"])


class CollegeBody(BaseModel):
    name: str = ""
    code: str = ""
    confirm: bool = False


class CourseBody(BaseModel):
    college_id: int | None = None
    parent_id: int | None = None
    name: str = ""
    course_code: str = ""
    kind: str = ""
    review_status: str = ""
    confirm: bool = False


def _raise(exc: CatalogError) -> None:
    if exc.extra:
        detail = {"message": exc.message, **exc.extra}
    else:
        detail = exc.message
    raise HTTPException(status_code=exc.status, detail=detail) from exc


@router.get("")
def academics(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    return list_academics(db)


@router.post("/colleges")
def add_college(body: CollegeBody, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return create_college(db, body.name, body.code, admin.id)
    except CatalogError as exc:
        _raise(exc)


@router.patch("/colleges/{college_id}")
def edit_college(
    college_id: int,
    body: CollegeBody,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        return update_college(db, college_id, body.name, body.code, body.confirm, admin.id)
    except CatalogError as exc:
        _raise(exc)


@router.delete("/colleges/{college_id}")
def remove_college(college_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return delete_college(db, college_id, admin.id)
    except CatalogError as exc:
        _raise(exc)


@router.post("/courses")
def add_course(body: CourseBody, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return create_course(
            db,
            body.college_id,
            body.name,
            body.course_code,
            admin.id,
            kind=body.kind,
            parent_id=body.parent_id,
            review_status=body.review_status,
        )
    except CatalogError as exc:
        _raise(exc)


@router.patch("/courses/{course_id}")
def edit_course(
    course_id: int,
    body: CourseBody,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        return update_course(
            db,
            course_id,
            body.college_id,
            body.name,
            body.course_code,
            body.confirm,
            admin.id,
            kind=body.kind,
            parent_id=body.parent_id,
            review_status=body.review_status,
        )
    except CatalogError as exc:
        _raise(exc)


@router.delete("/courses/{course_id}")
def remove_course(course_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return delete_course(db, course_id, admin.id)
    except CatalogError as exc:
        _raise(exc)

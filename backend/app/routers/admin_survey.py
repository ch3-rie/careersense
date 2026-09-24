from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import require_admin
from app.models import Account, SurveyVersion
from app.schemas import SurveyDraftIn, SurveyPublishIn, SurveySettingsIn
from app.services.survey import (
    ensure_gts_survey,
    get_version,
    publish_draft,
    restore_version,
    save_draft,
    save_settings,
    serialize_survey,
)
from app.survey_default import ADDABLE_TYPES, QUESTION_TYPE_LABELS

router = APIRouter(prefix="/api/admin/survey", tags=["admin-survey"])


def _payload(db: Session, row):
    versions = (
        db.query(SurveyVersion)
        .options(joinedload(SurveyVersion.publisher))
        .filter(SurveyVersion.survey_id == row.id)
        .order_by(SurveyVersion.version_number.desc())
        .all()
    )
    data = serialize_survey(row, versions)
    data["question_types"] = QUESTION_TYPE_LABELS
    data["addable_types"] = ADDABLE_TYPES
    return data


@router.get("")
def get_survey(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = ensure_gts_survey(db)
    db.commit()
    db.refresh(row)
    return _payload(db, row)


@router.put("/draft")
def put_draft(payload: SurveyDraftIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = save_draft(db, admin, payload.survey_schema, auto=payload.auto)
    return {"ok": True, "message": "All changes saved", **_payload(db, row)}


@router.put("/settings")
def put_settings(payload: SurveySettingsIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = save_settings(db, admin, payload.model_dump(exclude_unset=True))
    return {"ok": True, "message": "Survey settings saved", **_payload(db, row)}


@router.post("/publish")
def publish(payload: SurveyPublishIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = publish_draft(db, admin, confirm_impact=payload.confirm_impact)
    return {"ok": True, "message": "Survey published successfully", **_payload(db, row)}


@router.get("/versions/{version_number}")
def read_version(version_number: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    return get_version(db, version_number)


@router.post("/versions/{version_number}/restore")
def restore(version_number: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = restore_version(db, admin, version_number)
    return {"ok": True, "message": f"Version {version_number} restored to draft", **_payload(db, row)}

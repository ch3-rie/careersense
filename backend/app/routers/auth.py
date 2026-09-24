import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import (
    CORE_GTS_SECTIONS,
    EMPLOYMENT_STATUS_OPTIONS,
    HOW_FOUND_FIRST_JOB,
    PRIVACY_NOTICE,
    SALARY_OPTIONS,
    TIME_TO_FIRST_JOB_OPTIONS,
    UNEMPLOYMENT_REASONS,
)
from app.db import get_db
from app.deps import get_current_user
from app.models import Account, RegistrationDraft, Resume, UniversityRecord
from app.rate_limit import enforce_rate_limit, forgot_limiter, login_limiter, password_limiter, pin_limiter, register_limiter
from app.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResendRequest,
    ForgotPasswordVerifyRequest,
    GtsPayload,
    LoginRequest,
    PasswordChangeRequest,
    ResetPasswordRequest,
    UserOut,
)
from app.security import (
    access_token_claims,
    create_access_token,
    create_registration_token,
    hash_password,
    require_registration_payload,
    verify_password,
)
from app.services.email.dispatch import send_notice
from app.services.files import assert_resume_size, contained_upload_path, save_draft_resume, unlink_contained_file, write_bytes

logger = logging.getLogger("careersense")
from app.services.gts import persist_tracer_submission
from app.services.parser import extract_resume_from_upload, map_to_gts_fields
from app.services.password_reset import request_pin, resend_pin, reset_password, verify_pin
from app.services.survey import (
    ensure_gts_survey,
    extras_payload,
    get_published_schema,
    require_survey_writable,
    survey_is_open,
    validate_required_answers,
)
from app.services.validation import (
    existing_account_message,
    normalize_email,
    student_id_in_use,
    validate_password_strength,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _norm(text: Optional[str]) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _names_match(record_first: str, parsed_first: str) -> bool:
    left = _norm(record_first)
    right = _norm(parsed_first)
    if not left or not right:
        return False
    if left == right:
        return True
    left_first = left.split()[0]
    right_first = right.split()[0]
    return left_first == right_first and (left.startswith(right) or right.startswith(left))


def match_university_record(db: Session, email: str, first_name: str = "", last_name: str = "", middle_name: str = "") -> Optional[UniversityRecord]:
    record = (
        db.query(UniversityRecord)
        .filter(UniversityRecord.personal_email.ilike(email.strip()))
        .first()
    )
    if record:
        return record
    if first_name and last_name:
        last = _norm(last_name)
        candidates = (
            db.query(UniversityRecord)
            .filter(UniversityRecord.last_name.ilike(last_name.strip()))
            .all()
        )
        for rec in candidates:
            if _norm(rec.last_name) != last:
                continue
            if not _names_match(rec.first_name, first_name):
                continue
            if not middle_name or _norm(rec.middle_name) == _norm(middle_name):
                return rec
    return None


def serialize_user(user: Account) -> dict:
    data = UserOut.model_validate(user).model_dump()
    profile = getattr(user, "profile", None)
    if profile:
        data["first_name"] = data.get("first_name") or profile.first_name or ""
        data["last_name"] = data.get("last_name") or profile.last_name or ""
    return data


def _delete_draft_file(draft: RegistrationDraft) -> None:
    unlink_contained_file(draft.stored_path)


def _purge_expired_drafts(db: Session) -> None:
    now = datetime.now(timezone.utc)
    expired = db.query(RegistrationDraft).filter(RegistrationDraft.expires_at <= now).all()
    for draft in expired:
        _delete_draft_file(draft)
        db.delete(draft)


def _matched_payload(record: Optional[UniversityRecord]) -> dict:
    return {
        "matched": bool(record),
        "student_id": record.student_id if record else None,
        "degree": record.degree if record else None,
        "year_graduated": record.year_graduated if record else None,
        "first_name": record.first_name if record else None,
        "last_name": record.last_name if record else None,
    }


def _load_registration_draft(db: Session, token: str) -> RegistrationDraft:
    payload = require_registration_payload(token)
    try:
        draft_id = int(payload.get("did"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Your resume review session is invalid. Please start registration again.",
        )
    draft = (
        db.query(RegistrationDraft)
        .filter(RegistrationDraft.id == draft_id)
        .with_for_update()
        .first()
    )
    if not draft:
        raise HTTPException(
            status_code=400,
            detail="No in-progress registration was found. Please upload your resume again.",
        )
    expires = draft.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        _delete_draft_file(draft)
        db.delete(draft)
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Your resume review session expired. Please upload your resume again.",
        )
    return draft


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, login_limiter, "login")
    try:
        email = normalize_email(str(payload.email))
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")
    user = db.query(Account).filter(Account.personal_email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")
    if user.role == "Admin" and user.status != "Active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This administrator account is inactive.")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(str(user.id), access_token_claims(user))
    match = None
    if user.linked_student_id:
        rec = db.get(UniversityRecord, user.linked_student_id)
        if rec:
            match = {
                "student_id": rec.student_id,
                "degree": rec.degree,
                "year_graduated": rec.year_graduated,
                "matched": True,
            }
    return {"access_token": token, "token_type": "bearer", "user": serialize_user(user), "matched_record": match}


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    privacy_consent: bool = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Parse the resume and start a draft. No alumni account is created until the GTS is submitted."""
    enforce_rate_limit(request, register_limiter, "register")
    email_clean = normalize_email(email)
    if not privacy_consent:
        raise HTTPException(status_code=400, detail="Privacy consent is required to create an account.")
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Password confirmation does not match.")
    validate_password_strength(password)
    existing = db.query(Account).filter(Account.personal_email == email_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail=existing_account_message(existing))

    _purge_expired_drafts(db)

    file_bytes = await resume.read()
    assert_resume_size(file_bytes)
    stored_path, original_name, stored_mime = save_draft_resume(resume, file_bytes)
    try:
        write_bytes(stored_path, file_bytes)
        parsed, parser_source, text = extract_resume_from_upload(original_name, file_bytes)
    except Exception:
        unlink_contained_file(stored_path)
        raise
    prefill = map_to_gts_fields(parsed)

    record = match_university_record(
        db,
        email_clean,
        parsed.get("first_name", ""),
        parsed.get("last_name", ""),
        parsed.get("middle_name", ""),
    )
    if record:
        prefill["degree"] = record.degree or prefill.get("degree")
        prefill["year_graduated"] = record.year_graduated or prefill.get("year_graduated")

    existing_draft = db.query(RegistrationDraft).filter(RegistrationDraft.personal_email == email_clean).first()
    if existing_draft:
        _delete_draft_file(existing_draft)
        db.delete(existing_draft)
        db.flush()

    draft = RegistrationDraft(
        personal_email=email_clean,
        password_hash=hash_password(password),
        linked_student_id=record.student_id if record else None,
        privacy_consent=True,
        original_filename=original_name,
        stored_path=str(stored_path),
        mime_type=stored_mime,
        extracted_text=text,
        parsed_json=parsed,
        parser_source=parser_source,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(draft)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        unlink_contained_file(stored_path)
        raise HTTPException(
            status_code=400,
            detail="A registration is already in progress for this email. Please wait a moment and try again.",
        )
    db.refresh(draft)

    return {
        "registration_token": create_registration_token(draft.id),
        "matched_record": _matched_payload(record),
        "parsed_resume": parsed,
        "gts_prefill": prefill,
        "parser_source": parser_source,
        "account_created": False,
    }


@router.post("/register/complete")
def complete_registration(payload: GtsPayload, request: Request, db: Session = Depends(get_db)):
    """Create the alumni account only after the Graduate Tracer Survey is submitted."""
    enforce_rate_limit(request, register_limiter, "register-complete")
    if not payload.registration_token:
        raise HTTPException(status_code=400, detail="Please upload your resume again, then submit the survey.")
    draft = _load_registration_draft(db, payload.registration_token)

    existing = db.query(Account).filter(Account.personal_email == draft.personal_email).first()
    if existing:
        raise HTTPException(status_code=400, detail=existing_account_message(existing))

    survey = payload.model_dump()
    extra = survey.pop("extra_answers", {}) or {}
    survey.pop("registration_token", None)
    survey.pop("resume_id", None)
    schema = get_published_schema(db)
    require_survey_writable(schema)
    validate_required_answers(schema, survey, extra)

    record = db.get(UniversityRecord, draft.linked_student_id) if draft.linked_student_id else None
    linked_id = draft.linked_student_id
    if student_id_in_use(db, linked_id):
        raise HTTPException(
            status_code=409,
            detail="This graduate record is already linked to another CareerSense account. Please contact the Alumni Office.",
        )
    user = Account(
        personal_email=draft.personal_email,
        password_hash=draft.password_hash,
        linked_student_id=linked_id,
        role="Alumni",
        status="Pending",
        is_verified=bool(record),
        privacy_consent=draft.privacy_consent,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This email or graduate record is already registered. Please sign in or contact the Alumni Office.",
        )

    stored = contained_upload_path(draft.stored_path)
    dest_dir = get_settings().upload_path / "resumes" / str(user.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if stored and stored.exists():
        final_path = dest_dir / stored.name
        stored.replace(final_path)
    else:
        final_path = dest_dir / "missing-resume.txt"

    resume_row = Resume(
        account_id=user.id,
        original_filename=draft.original_filename,
        stored_path=str(final_path),
        mime_type=draft.mime_type,
        extracted_text=draft.extracted_text,
        parsed_json=draft.parsed_json or {},
        parser_source=draft.parser_source,
    )
    db.add(resume_row)
    db.flush()

    submission = persist_tracer_submission(db, user, survey, extra_answers=extra, resume_id=resume_row.id)
    db.delete(draft)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This email or graduate record is already registered. Please sign in or contact the Alumni Office.",
        )
    db.refresh(user)
    db.refresh(submission)
    recipient_name = " ".join(
        part for part in [str(survey.get("first_name") or "").strip(), str(survey.get("last_name") or "").strip()] if part
    )
    try:
        send_notice(
            db,
            kind="registration_received",
            to_address=user.personal_email,
            account_id=user.id,
            name=recipient_name,
            subject="Registration received",
            headline="Registration received",
            intro=(
                "CareerSense received your registration and Graduate Tracer Survey. "
                "The Alumni Office will review your account before you can use the alumni portal."
            ),
            path="/login",
            cta="Check your account status",
        )
        db.commit()
    except Exception:
        logger.exception("Registration received email failed")
        db.rollback()

    token = create_access_token(str(user.id), access_token_claims(user))
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user),
        "submission_id": submission.id,
        "alignment_status": submission.alignment_status,
        "alignment_score": submission.alignment_score,
        "status": user.status,
        "message": "Tracer information saved. The Alumni Office will review your registration.",
    }


@router.get("/me")
def me(user: Account = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = user.profile
    return {
        "user": serialize_user(user),
        "profile": {
            "first_name": profile.first_name if profile else "",
            "middle_name": profile.middle_name if profile else "",
            "last_name": profile.last_name if profile else "",
            "degree": profile.degree if profile else "",
            "year_graduated": profile.year_graduated if profile else "",
            "country_residence": profile.country_residence if profile else "Philippines",
        },
    }


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    user: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(request, password_limiter, f"password:{user.id}")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different.")
    validate_password_strength(payload.new_password)
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.must_change_password = False
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    token = create_access_token(str(user.id), access_token_claims(user))
    return {"ok": True, "message": "Password updated.", "access_token": token, "token_type": "bearer"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, forgot_limiter, "forgot")
    return request_pin(db, str(payload.email))


@router.post("/forgot-password/resend")
def forgot_password_resend(payload: ForgotPasswordResendRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, forgot_limiter, "forgot-resend")
    return resend_pin(db, str(payload.email))


@router.post("/forgot-password/verify")
def forgot_password_verify(payload: ForgotPasswordVerifyRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, pin_limiter, "forgot-verify")
    return verify_pin(db, str(payload.email), payload.pin)


@router.post("/reset-password")
def forgot_password_reset(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, password_limiter, "reset-password")
    return reset_password(db, payload.reset_token, payload.new_password)


@router.get("/options")
def public_options(db: Session = Depends(get_db)):
    row = ensure_gts_survey(db)
    db.commit()
    schema = get_published_schema(db)
    extras = extras_payload(schema)
    settings = get_settings()
    published_at = row.published_at.isoformat() if row.published_at else None
    return {
        "privacy_notice": PRIVACY_NOTICE,
        "salary_options": SALARY_OPTIONS,
        "employment_status_options": EMPLOYMENT_STATUS_OPTIONS,
        "time_to_first_job_options": TIME_TO_FIRST_JOB_OPTIONS,
        "unemployment_reasons": UNEMPLOYMENT_REASONS,
        "how_found_first_job": HOW_FOUND_FIRST_JOB,
        "core_sections": CORE_GTS_SECTIONS,
        "office_contact": {
            "name": settings.oaaps_office_name,
            "email": settings.oaaps_email or None,
            "phone": settings.oaaps_phone or None,
            "hours": settings.oaaps_hours or None,
            "location": settings.oaaps_location or None,
        },
        "survey": schema,
        "survey_version": int(row.published_version or 0),
        "survey_published_at": published_at,
        "survey_open": survey_is_open(schema),
        "allow_alumni_edit": bool(schema.get("allow_alumni_edit", True)),
        "supplementary_questions": extras,
    }

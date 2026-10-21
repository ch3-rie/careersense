from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm.attributes import flag_modified
from fastapi.responses import FileResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_active_alumni, require_pending_or_active_alumni
from app.rate_limit import enforce_rate_limit, qr_lookup_limiter
from app.services.alumni_qr import (
    alumni_qr_identity,
    office_contact,
    qr_svg,
    verified_alumni_for_token,
    verify_url,
)
from app.models import Account, AlumniCertification, AlumniSkill, Resume, TracerSubmission
from app.schemas import (
    AwardIn,
    CardApplicationIn,
    CertificationIn,
    EmploymentStatusIn,
    GtsPayload,
    JobIn,
    ProfileUpdateIn,
    SeminarIn,
    StudyIn,
)
from app.services.alignment import analyze_career_alignment, alignment_score
from app.services.alumni_hub import (
    apply_card_application,
    assemble_profile,
    card_workspace,
    claim_perk,
    ensure_card,
    ensure_starter_notifications,
    list_notifications,
    list_perks,
    mark_all_notifications_read,
    mark_notification_read,
    update_contact_profile,
)
from app.services.employment import resolve_current_employment
from app.services.files import (
    assert_resume_size,
    resolve_stored_file,
    safe_download_name,
    save_cover_photo,
    save_profile_photo,
    save_resume_file,
    unlink_contained_file,
    write_bytes,
)
from app.services.gts import persist_tracer_submission
from app.services.jobs import create_job, delete_job, ensure_job_timeline, update_job
from app.services.studies import create_study, delete_study, serialize_studies, update_study
from app.services.parser import extract_resume_from_upload, map_to_gts_fields
from app.services.parser_course import select_current_experience
from app.services.profile_completion import refresh_alumni_progress
from app.services.resume_pdf import (
    build_resume_pdf,
    merge_resume_content,
    profile_from_document,
    resume_document_from_profile,
    resume_filename,
    resume_preview,
    sanitize_resume_document,
)
from app.services.profile_records import (
    certification_file,
    create_award,
    create_certification,
    create_seminar,
    delete_award,
    delete_certification,
    delete_seminar,
    replace_certificate,
    serialize_activity,
    set_employment_status,
    update_award,
    update_certification,
    update_seminar,
)
from app.services.profile_updates import evaluate_profile_update_completions
from app.services.survey import get_published_schema, require_survey_writable, validate_required_answers

router = APIRouter(prefix="/api/alumni", tags=["alumni"])
public_router = APIRouter(prefix="/api/public", tags=["public"])


def _latest_submission(db: Session, account_id: int) -> TracerSubmission | None:
    return (
        db.query(TracerSubmission)
        .filter(TracerSubmission.account_id == account_id)
        .order_by(TracerSubmission.submitted_at.desc())
        .first()
    )


@router.get("/dashboard")
def dashboard(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    evaluate_profile_update_completions(db, user)
    return assemble_profile(db, user)


@router.put("/profile")
def edit_profile(
    payload: ProfileUpdateIn,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    update_contact_profile(db, user, payload)
    evaluate_profile_update_completions(db, user)
    return assemble_profile(db, user, notify_badges=True)


@router.post("/profile/photo")
async def upload_profile_photo(
    photo: UploadFile = File(...),
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    profile = user.profile
    if profile is None:
        raise HTTPException(status_code=400, detail="No alumni profile is on file.")
    file_bytes = await photo.read()
    stored, mime = save_profile_photo(user.id, file_bytes)
    previous = profile.photo_path
    profile.photo_path = str(stored)
    profile.photo_mime = mime
    db.commit()
    if previous and previous != str(stored):
        unlink_contained_file(previous)
    evaluate_profile_update_completions(db, user)
    return assemble_profile(db, user, notify_badges=True)


@router.delete("/profile/photo")
def delete_profile_photo(
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    profile = user.profile
    if profile is None:
        raise HTTPException(status_code=400, detail="No alumni profile is on file.")
    previous = profile.photo_path
    if not previous:
        raise HTTPException(status_code=404, detail="No profile photo on file.")
    profile.photo_path = ""
    profile.photo_mime = ""
    db.commit()
    unlink_contained_file(previous)
    evaluate_profile_update_completions(db, user)
    return assemble_profile(db, user, notify_badges=True)


@router.get("/profile/photo")
def profile_photo(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    profile = user.profile
    if not profile or not profile.photo_path:
        raise HTTPException(status_code=404, detail="No profile photo on file.")
    path = resolve_stored_file(profile.photo_path, missing_detail="Profile photo is no longer on disk.")
    return FileResponse(path, media_type=profile.photo_mime or "image/jpeg")


@router.post("/profile/cover")
async def upload_cover_photo(
    cover: UploadFile = File(...),
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    profile = user.profile
    if profile is None:
        raise HTTPException(status_code=400, detail="No alumni profile is on file.")
    file_bytes = await cover.read()
    stored, mime = save_cover_photo(user.id, file_bytes)
    previous = profile.cover_path
    profile.cover_path = str(stored)
    profile.cover_mime = mime
    db.commit()
    if previous and previous != str(stored):
        unlink_contained_file(previous)
    return assemble_profile(db, user)


@router.delete("/profile/cover")
def delete_cover_photo(
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    profile = user.profile
    if profile is None:
        raise HTTPException(status_code=400, detail="No alumni profile is on file.")
    previous = profile.cover_path
    if not previous:
        raise HTTPException(status_code=404, detail="No cover photo on file.")
    profile.cover_path = ""
    profile.cover_mime = ""
    db.commit()
    unlink_contained_file(previous)
    return assemble_profile(db, user)


@router.get("/profile/cover")
def cover_photo(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    profile = user.profile
    if not profile or not profile.cover_path:
        raise HTTPException(status_code=404, detail="No cover photo on file.")
    path = resolve_stored_file(profile.cover_path, missing_detail="Cover photo is no longer on disk.")
    return FileResponse(path, media_type=profile.cover_mime or "image/jpeg")


@router.get("/profile-completion")
@router.get("/completion")
def profile_completion(
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    evaluate_profile_update_completions(db, user)
    progress = refresh_alumni_progress(db, user, notify=False)
    try:
        db.commit()
    except Exception:
        db.rollback()
    if progress is None:
        raise HTTPException(status_code=503, detail="Profile completion is temporarily unavailable.")
    return progress


@router.get("/achievements")
def alumni_achievements(
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    evaluate_profile_update_completions(db, user)
    progress = refresh_alumni_progress(db, user, notify=False)
    try:
        db.commit()
    except Exception:
        db.rollback()
    if progress is None:
        raise HTTPException(status_code=503, detail="Achievements are temporarily unavailable.")
    return {
        "achievements": progress.get("achievements") or [],
        "earned_count": int(progress.get("earned_count") or 0),
        "total_count": int(progress.get("total_count") or 0),
        "percent": int(progress.get("percent") or 0),
        "percentage": int(progress.get("percent") or 0),
        "is_complete": bool(progress.get("is_complete")),
        "next_achievement": progress.get("next_achievement"),
    }


@router.get("/notifications")
def notifications(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    evaluate_profile_update_completions(db, user)
    card = ensure_card(db, user)
    latest = _latest_submission(db, user.id)
    ensure_starter_notifications(db, user, card, latest is not None)
    refresh_alumni_progress(db, user, notify=False)
    db.commit()
    notes = list_notifications(db, user)
    return {
        "notifications": notes,
        "unread_count": sum(1 for item in notes if not item["read"]),
    }


@router.post("/notifications/read-all")
def read_all_notifications(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return {"notifications": mark_all_notifications_read(db, user)}


@router.post("/notifications/{notification_id}/read")
def read_notification(
    notification_id: int,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    return {"notifications": mark_notification_read(db, user, notification_id)}


@router.get("/perks")
def perks(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return {"perks": list_perks(db, user)}


@router.get("/perks/{perk_id}/image")
def perk_image(perk_id: int, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    from app.models import AlumniPerk

    perk = db.get(AlumniPerk, perk_id)
    if not perk or not perk.active or not perk.image_path:
        raise HTTPException(status_code=404, detail="Image not found.")
    path = resolve_stored_file(perk.image_path, missing_detail="Image not found.")
    return FileResponse(path, media_type=perk.image_mime or "image/jpeg")


@router.post("/perks/{perk_id}/claim")
def redeem_perk(perk_id: int, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return {"perks": claim_perk(db, user, perk_id)}


@router.get("/office")
def alumni_office(_user: Account = Depends(require_active_alumni)):
    return office_contact()


@router.get("/qr")
def alumni_qr(user: Account = Depends(require_active_alumni)):
    return alumni_qr_identity(user)


@router.get("/qr/image")
def alumni_qr_image(user: Account = Depends(require_active_alumni)):
    svg = qr_svg(verify_url(user.id))
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "private, max-age=3600"})


@public_router.get("/alumni-qr/{token}")
def verify_alumni_qr(token: str, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, qr_lookup_limiter, "alumni-qr")
    user = verified_alumni_for_token(db, token)
    if user is None:
        raise HTTPException(status_code=404, detail="This QR code could not be verified.")
    return alumni_qr_identity(user)


@router.get("/card")
def alumni_card(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return card_workspace(db, user)


@router.post("/card/apply")
def submit_card_application(
    payload: CardApplicationIn,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    result = apply_card_application(db, user, payload)
    evaluate_profile_update_completions(db, user)
    refresh_alumni_progress(db, user, notify=True)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return result


@router.get("/jobs")
def list_jobs(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return {"jobs": ensure_job_timeline(db, user)}


@router.post("/jobs")
def add_job(payload: JobIn, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    jobs = create_job(db, user, payload)
    evaluate_profile_update_completions(db, user)
    refresh_alumni_progress(db, user, notify=True)
    db.commit()
    return {"jobs": jobs}


@router.put("/jobs/{job_id}")
def edit_job(
    job_id: int,
    payload: JobIn,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    jobs = update_job(db, user, job_id, payload)
    evaluate_profile_update_completions(db, user)
    refresh_alumni_progress(db, user, notify=True)
    db.commit()
    return {"jobs": jobs}


@router.delete("/jobs/{job_id}")
def remove_job(job_id: int, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    jobs = delete_job(db, user, job_id)
    evaluate_profile_update_completions(db, user)
    refresh_alumni_progress(db, user, notify=True)
    db.commit()
    return {"jobs": jobs}


@router.get("/studies")
def list_studies(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return {"studies": serialize_studies(db, user.id)}


@router.post("/studies")
def add_study(payload: StudyIn, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    studies = create_study(db, user, payload)
    evaluate_profile_update_completions(db, user)
    refresh_alumni_progress(db, user, notify=True)
    db.commit()
    return {"studies": studies}


@router.put("/studies/{study_id}")
def edit_study(
    study_id: int,
    payload: StudyIn,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    studies = update_study(db, user, study_id, payload)
    evaluate_profile_update_completions(db, user)
    refresh_alumni_progress(db, user, notify=True)
    db.commit()
    return {"studies": studies}


@router.delete("/studies/{study_id}")
def remove_study(study_id: int, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    studies = delete_study(db, user, study_id)
    evaluate_profile_update_completions(db, user)
    refresh_alumni_progress(db, user, notify=True)
    db.commit()
    return {"studies": studies}


@router.put("/employment-status")
@router.put("/employment-note")
def save_employment_status(
    payload: EmploymentStatusIn,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    status = set_employment_status(db, user, payload)
    refresh_alumni_progress(db, user, notify=False)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return status


@router.post("/seminars")
def add_seminar(payload: SeminarIn, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return {"seminars": create_seminar(db, user, payload)}


@router.put("/seminars/{seminar_id}")
def edit_seminar(
    seminar_id: int,
    payload: SeminarIn,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    return {"seminars": update_seminar(db, user, seminar_id, payload)}


@router.delete("/seminars/{seminar_id}")
def remove_seminar(seminar_id: int, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return {"seminars": delete_seminar(db, user, seminar_id)}


@router.post("/certifications")
async def add_certification(
    name: str = Form(""),
    awarded_on: str = Form(""),
    awarding_body: str = Form(""),
    verification_url: str = Form(""),
    certificate: UploadFile = File(...),
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    try:
        payload = CertificationIn(
            name=name,
            awarded_on=awarded_on,
            awarding_body=awarding_body,
            verification_url=verification_url,
        )
    except ValidationError as exc:
        message = exc.errors()[0].get("msg") if exc.errors() else ""
        raise HTTPException(
            status_code=400,
            detail=message or "Certification name, awarding body, and award date are required.",
        ) from exc
    file_bytes = await certificate.read()
    rows = create_certification(db, user, payload, file_bytes, certificate.filename or "")
    return {"certifications": rows}


@router.put("/certifications/{certification_id}")
def edit_certification(
    certification_id: int,
    payload: CertificationIn,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    return {"certifications": update_certification(db, user, certification_id, payload)}


@router.post("/certifications/{certification_id}/file")
async def replace_certification_file(
    certification_id: int,
    certificate: UploadFile = File(...),
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    file_bytes = await certificate.read()
    rows = replace_certificate(db, user, certification_id, file_bytes, certificate.filename or "")
    return {"certifications": rows}


@router.get("/certifications/{certification_id}/file")
def alumni_certification_file(
    certification_id: int,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    row = certification_file(db, certification_id, account_id=user.id)
    path = resolve_stored_file(row.certificate_path, missing_detail="Certificate file is no longer on disk.")
    return FileResponse(
        path,
        media_type=row.certificate_mime or "application/octet-stream",
        filename=safe_download_name(row.certificate_filename or "certificate"),
        content_disposition_type="inline",
    )


@router.delete("/certifications/{certification_id}")
def remove_certification(
    certification_id: int,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    return {"certifications": delete_certification(db, user, certification_id)}


@router.post("/awards")
def add_award(payload: AwardIn, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return {"awards": create_award(db, user, payload)}


@router.put("/awards/{award_id}")
def edit_award(
    award_id: int,
    payload: AwardIn,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    return {"awards": update_award(db, user, award_id, payload)}


@router.delete("/awards/{award_id}")
def remove_award(award_id: int, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return {"awards": delete_award(db, user, award_id)}


@router.get("/analytics")
def analytics(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    alignment = user.alignment
    submissions = (
        db.query(TracerSubmission)
        .filter(TracerSubmission.account_id == user.id)
        .order_by(TracerSubmission.submitted_at.desc())
        .all()
    )
    history = [
        {
            "id": row.id,
            "submitted_at": row.submitted_at,
            "alignment_status": row.alignment_status,
            "alignment_score": row.alignment_score,
            "job_title": resolve_current_employment(row.data_json or {}).occupation,
            "employer": resolve_current_employment(row.data_json or {}).employer,
            "preview": {
                "degree": (row.data_json or {}).get("degree"),
                "soc_code": row.soc_code,
                "soc_description": (row.data_json or {}).get("soc_description"),
            },
            "data": row.data_json,
            "extra_answers": row.extra_answers,
        }
        for row in submissions
    ]
    return {
        "score": alignment.overall_match_score if alignment else (history[0]["alignment_score"] if history else 0),
        "status": alignment.alignment_justification if alignment else (history[0]["alignment_status"] if history else "Unknown"),
        "justification": alignment.justification_detail if alignment else "",
        "suggested_paths": alignment.suggested_career_paths if alignment else [],
        "history": history,
    }


@router.get("/profile")
def profile(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    latest = _latest_submission(db, user.id)
    skills = [s.skill_name for s in db.query(AlumniSkill).filter(AlumniSkill.account_id == user.id).all()]
    studies = serialize_studies(db, user.id)
    profile = user.profile
    completion = refresh_alumni_progress(db, user, notify=False)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return {
        "user": {
            "id": user.id,
            "email": user.personal_email,
            "student_id": user.linked_student_id,
            "status": user.status,
            "role": user.role,
            "created_at": user.created_at,
            "rejection_reason": user.rejection_reason,
        },
        "profile": {
            "first_name": profile.first_name if profile else "",
            "middle_name": profile.middle_name if profile else "",
            "last_name": profile.last_name if profile else "",
            "husband_surname": profile.husband_surname if profile else "",
            "country_residence": profile.country_residence if profile else "Philippines",
            "degree": profile.degree if profile else "",
            "year_graduated": profile.year_graduated if profile else "",
            "phone": (profile.phone if profile else "") or "",
            "city": (profile.city if profile else "") or "",
            "address": (profile.address if profile else "") or "",
            "bio": (profile.bio if profile else "") or "",
            "has_photo": bool(profile and profile.photo_path),
            "has_cover": bool(profile and profile.cover_path),
            "guardian_type": profile.guardian_type if profile else "",
            "guardian_degree_completed": profile.guardian_degree_completed if profile else None,
        },
        "skills": skills,
        "further_studies": studies,
        "latest_gts": latest.data_json if latest else {},
        "extra_answers": latest.extra_answers if latest else {},
        "latest_submitted_at": latest.submitted_at if latest else None,
        "completion": completion,
    }


@router.post("/gts")
def submit_gts(
    payload: GtsPayload,
    user: Account = Depends(require_pending_or_active_alumni),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    extra = data.pop("extra_answers", {}) or {}
    schema = get_published_schema(db)
    require_survey_writable(schema, alumni_status=user.status)
    validate_required_answers(schema, data, extra)
    resume_id = data.get("resume_id")
    submission = persist_tracer_submission(db, user, data, extra_answers=extra, resume_id=resume_id)
    db.commit()
    db.refresh(submission)
    if user.status == "Active":
        evaluate_profile_update_completions(db, user)
        refresh_alumni_progress(db, user, notify=True)
        db.commit()
    return {
        "ok": True,
        "submission_id": submission.id,
        "alignment_status": submission.alignment_status,
        "alignment_score": submission.alignment_score,
        "status": user.status,
        "message": "Tracer information saved. The Alumni Office will review your registration."
        if user.status == "Pending"
        else "Tracer record updated.",
    }


def _resume_profile(db: Session, user: Account) -> dict:
    profile = user.profile
    record = user.university_record
    activity = serialize_activity(db, user.id)
    jobs = ensure_job_timeline(db, user)
    skills = [row.skill_name for row in db.query(AlumniSkill).filter(AlumniSkill.account_id == user.id).all() if row.skill_name]
    if not skills:
        latest = _latest_submission(db, user.id)
        raw_skills = (latest.data_json or {}).get("skills") if latest else []
        skills = [str(item).strip() for item in (raw_skills or []) if str(item).strip()]
    name = " ".join(
        part.strip()
        for part in [
            profile.first_name if profile else "",
            profile.middle_name if profile else "",
            profile.last_name if profile else "",
        ]
        if part and part.strip()
    )
    covered = {
        row.id: list(row.skills_covered or [])
        for row in db.query(AlumniCertification).filter(AlumniCertification.account_id == user.id)
    }
    certifications = []
    for row in activity.get("certifications") or []:
        item = dict(row)
        item["skills"] = covered.get(row.get("id"), [])
        certifications.append(item)
    uploads = [
        {
            "parser_source": resume.parser_source,
            "parsed": resume.parsed_json if isinstance(resume.parsed_json, dict) else {},
            "text": resume.extracted_text or "",
        }
        for resume in (
            db.query(Resume)
            .filter(Resume.account_id == user.id)
            .order_by(Resume.created_at.desc(), Resume.id.desc())
        )
    ]
    return merge_resume_content(
        {
            "name": name or user.personal_email,
            "email": user.personal_email or "",
            "phone": (profile.phone if profile else "") or "",
            "address": (profile.address if profile else "") or "",
            "city": (profile.city if profile else "") or "",
            "country": (profile.country_residence if profile else "") or "",
            "bio": (profile.bio if profile else "") or "",
            "degree": (profile.degree if profile else "") or (record.degree if record else ""),
            "college": record.college if record else "",
            "year_graduated": (profile.year_graduated if profile else "") or (record.year_graduated if record else ""),
            "studies": serialize_studies(db, user.id),
            "jobs": jobs,
            "skills": skills,
            "certifications": certifications,
            "seminars": activity.get("seminars") or [],
            "awards": activity.get("awards") or [],
        },
        uploads,
    )


def _saved_resume_document(user: Account) -> dict | None:
    profile = user.profile
    saved = profile.resume_document if profile is not None else None
    if isinstance(saved, dict) and saved.get("sections") is not None:
        return sanitize_resume_document(saved)
    return None


def _export_source(db: Session, user: Account) -> dict:
    saved = _saved_resume_document(user)
    document = saved if saved is not None else resume_document_from_profile(_resume_profile(db, user))
    return profile_from_document(document)


@router.get("/resume/document")
def resume_document(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    saved = _saved_resume_document(user)
    if saved is not None:
        return {"saved": True, "notices": [], "document": saved}
    failed = (
        db.query(Resume)
        .filter(Resume.account_id == user.id, Resume.parser_source.in_(["failed", "empty"]))
        .count()
    )
    notices = []
    if failed:
        notices.append("One uploaded file could not be read. This draft uses your saved profile and any uploaded files that could be read.")
    return {"saved": False, "notices": notices, "document": resume_document_from_profile(_resume_profile(db, user))}


@router.put("/resume/document")
def save_resume_document(
    payload: dict,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    if user.profile is None:
        raise HTTPException(status_code=400, detail="No alumni profile is on file.")
    document = sanitize_resume_document(payload)
    user.profile.resume_document = document
    flag_modified(user.profile, "resume_document")
    db.commit()
    return {"saved": True, "document": document}


@router.get("/resume/preview")
def preview_resume(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    return resume_preview(_export_source(db, user))


@router.get("/resume/export")
def export_resume(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    source = _export_source(db, user)
    pdf = build_resume_pdf(source)
    filename = safe_download_name(resume_filename(source.get("name") or ""))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/resumes")
def list_resumes(user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    rows = (
        db.query(Resume)
        .filter(Resume.account_id == user.id)
        .order_by(Resume.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "original_filename": r.original_filename,
            "parser_source": r.parser_source,
            "created_at": r.created_at,
            "parsed": r.parsed_json,
        }
        for r in rows
    ]


@router.post("/resumes")
async def upload_resume(
    resume: UploadFile = File(...),
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    file_bytes = await resume.read()
    assert_resume_size(file_bytes)
    stored_path, original_name, stored_mime = save_resume_file(user.id, resume, file_bytes)
    try:
        write_bytes(stored_path, file_bytes)
        parsed, source, text = extract_resume_from_upload(original_name, file_bytes)
    except Exception:
        unlink_contained_file(stored_path)
        raise
    prefill = map_to_gts_fields(parsed)
    row = Resume(
        account_id=user.id,
        original_filename=original_name,
        stored_path=str(stored_path),
        mime_type=stored_mime,
        extracted_text=text,
        parsed_json=parsed,
        parser_source=source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    job = ""
    job_context = ""
    if (parsed.get("is_currently_employed") or prefill.get("is_currently_employed")) == "Yes":
        current = select_current_experience(parsed.get("experiences") or [])
        job = current.get("job_title") or prefill.get("pres_occ") or ""
        job_context = " ".join(part for part in [current.get("description"), current.get("employer")] if part)
    degree = prefill.get("degree") or (user.profile.degree if user.profile else "")
    status, detail, soc, suggestions = analyze_career_alignment(db, job, degree, job_context=job_context)
    course = parsed.get("course_alignment") if isinstance(parsed.get("course_alignment"), dict) else {}
    return {
        "resume_id": row.id,
        "parser_source": source,
        "parsed": parsed,
        "gts_prefill": {**prefill, "resume_id": row.id},
        "alignment": {
            "status": status,
            "detail": detail,
            "score": alignment_score(status),
            "soc_code": soc.soc_code if soc else None,
            "soc_description": soc.description if soc else None,
            "suggested_paths": suggestions,
            "official": False,
            "source": "resume_preview",
        },
        "parser_course_alignment": course or None,
    }


@router.get("/resumes/{resume_id}/file")
def download_own_resume(
    resume_id: int,
    user: Account = Depends(require_active_alumni),
    db: Session = Depends(get_db),
):
    row = db.get(Resume, resume_id)
    if not row or row.account_id != user.id:
        raise HTTPException(status_code=404, detail="Resume not found.")
    path = resolve_stored_file(row.stored_path, missing_detail="Resume file is no longer on disk.")
    return FileResponse(path, filename=safe_download_name(row.original_filename))


@router.post("/alignment/preview")
def preview_alignment(payload: dict, user: Account = Depends(require_active_alumni), db: Session = Depends(get_db)):
    current = resolve_current_employment(payload)
    job = payload.get("job_title") or current.occupation
    degree = payload.get("degree") or (user.profile.degree if user.profile else "")
    status, detail, soc, suggestions = analyze_career_alignment(db, job, degree, job_context=current.employer)
    return {
        "status": status,
        "detail": detail,
        "score": alignment_score(status),
        "soc_code": soc.soc_code if soc else None,
        "soc_description": soc.description if soc else None,
        "suggested_paths": suggestions,
    }

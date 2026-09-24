import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.constants import CORE_GTS_SECTIONS, QUESTION_TYPES
from app.db import get_db
from app.deps import require_admin
from app.models import (
    Account,
    AdminLog,
    AlignmentResult,
    AlumniCard,
    AlumniProfile,
    FurtherStudy,
    JobTitleMapping,
    Resume,
    SocCode,
    TracerSubmission,
    UniversityRecord,
)
from app.routers.auth import _norm, match_university_record
from app.schemas import MappingIn, QuestionIn, QuestionUpdate, RejectRequest, SocIn, UniversityRecordIn
from app.services.academic_filters import (
    academic_catalog,
    apply_registry_academic_filters,
    apply_tracer_academic_filters,
)
from app.services.alignment import invalidate_soc_cache
from app.services.email import send_account_status_email
from app.services.employment import resolve_current_employment
from app.services.files import resolve_stored_file, safe_download_name
from app.services.oaaps_docx import render_oaaps_docx
from app.services.reports import (
    _relatedness,
    build_oaaps_report,
    filter_options,
    employment_analytics,
    latest_submissions,
    parse_report_date,
)
from app.services.survey import add_legacy_extra, delete_legacy_extra, ensure_gts_survey, extras_payload, save_draft
from app.services.validation import csv_safe, student_id_in_use
from app.survey_default import clone_schema, iter_questions

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _log(db: Session, admin_id: int, action: str, target_id, old=None, new=None):
    db.add(
        AdminLog(
            admin_id=admin_id,
            action_type=action,
            target_id=str(target_id),
            old_value=old,
            new_value=new,
        )
    )


def _account_name(account: Account) -> str:
    if account.profile:
        parts = [account.profile.first_name, account.profile.middle_name, account.profile.last_name]
        name = " ".join(p for p in parts if p).strip()
        if name:
            return name
    return account.personal_email


@router.get("/dashboard")
def dashboard(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    alumni_q = db.query(Account).filter(Account.role == "Alumni")
    total_registered = alumni_q.count()
    pending = alumni_q.filter(Account.status == "Pending").count()
    approved = alumni_q.filter(Account.status == "Active").count()
    rejected = alumni_q.filter(Account.status == "Rejected").count()
    submissions = db.query(TracerSubmission).count()
    aligned = db.query(AlignmentResult).filter(AlignmentResult.alignment_justification == "Aligned").count()
    unknown = db.query(AlignmentResult).filter(AlignmentResult.alignment_justification == "Unknown").count()
    misaligned = db.query(AlignmentResult).filter(AlignmentResult.alignment_justification == "Misaligned").count()
    pending_cards = (
        db.query(AlumniCard)
        .join(Account, Account.id == AlumniCard.account_id)
        .filter(Account.role == "Alumni", AlumniCard.status == "ForVerification")
        .count()
    )
    classified = aligned + unknown + misaligned
    percent_aligned = round((aligned / classified) * 100, 1) if classified else 0

    trend_rows = (
        db.query(func.date(TracerSubmission.submitted_at), func.count(TracerSubmission.id))
        .group_by(func.date(TracerSubmission.submitted_at))
        .order_by(func.date(TracerSubmission.submitted_at))
        .all()
    )
    return {
        "pending_approvals": pending,
        "pending_card_applications": pending_cards,
        "total_submissions": submissions,
        "approved_alumni": approved,
        "rejected_alumni": rejected,
        "total_registered": total_registered,
        "percent_aligned": percent_aligned,
        "avg_alignment": percent_aligned,
        "alignment_distribution": {"Aligned": aligned, "Unknown": unknown, "Misaligned": misaligned},
        "submission_trend": [{"date": str(d), "count": c} for d, c in trend_rows if d],
    }


@router.get("/approvals")
def approvals(
    page: int = 1,
    page_size: int = 10,
    q: str = "",
    sort_by: str = "created",
    sort_dir: str = "desc",
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    page = max(1, page)
    page_size = min(50, max(5, page_size))
    query = (
        db.query(Account)
        .outerjoin(AlumniProfile, AlumniProfile.account_id == Account.id)
        .options(joinedload(Account.profile), joinedload(Account.university_record))
        .filter(Account.role == "Alumni", Account.status == "Pending")
    )
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            or_(
                Account.personal_email.ilike(like),
                Account.linked_student_id.ilike(like),
                AlumniProfile.first_name.ilike(like),
                AlumniProfile.middle_name.ilike(like),
                AlumniProfile.last_name.ilike(like),
            )
        )
    key = (sort_by or "created").lower()
    descending = (sort_dir or "desc").lower() != "asc"
    if key == "email":
        order_col = func.lower(Account.personal_email)
    elif key == "name":
        order_col = func.lower(func.coalesce(AlumniProfile.last_name, Account.personal_email))
    else:
        order_col = Account.created_at
    query = query.order_by(order_col.desc() if descending else order_col.asc(), Account.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for user in rows:
        latest = (
            db.query(TracerSubmission)
            .filter(TracerSubmission.account_id == user.id)
            .order_by(TracerSubmission.submitted_at.desc())
            .first()
        )
        resume = (
            db.query(Resume)
            .filter(Resume.account_id == user.id)
            .order_by(Resume.created_at.desc())
            .first()
        )
        items.append({
            "id": user.id,
            "email": user.personal_email,
            "student_id": user.linked_student_id,
            "created_at": user.created_at,
            "name": _account_name(user),
            "degree": user.profile.degree if user.profile else "",
            "year_graduated": user.profile.year_graduated if user.profile else "",
            "matched": bool(user.linked_student_id),
            "has_submission": bool(latest),
            "resume_id": resume.id if resume else None,
            "resume_filename": resume.original_filename if resume else None,
        })
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "q": term,
        "sort_by": key if key in {"name", "email", "created"} else "created",
        "sort_dir": "desc" if descending else "asc",
    }


@router.get("/approvals/{account_id}")
def approval_detail(account_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(Account, account_id)
    if not user or user.role != "Alumni":
        raise HTTPException(status_code=404, detail="Alumni account not found.")
    latest = (
        db.query(TracerSubmission)
        .filter(TracerSubmission.account_id == user.id)
        .order_by(TracerSubmission.submitted_at.desc())
        .first()
    )
    studies = db.query(FurtherStudy).filter(FurtherStudy.account_id == user.id).all()
    resumes = db.query(Resume).filter(Resume.account_id == user.id).order_by(Resume.created_at.desc()).all()
    return {
        "account": {
            "id": user.id,
            "email": user.personal_email,
            "status": user.status,
            "student_id": user.linked_student_id,
            "created_at": user.created_at,
            "is_verified": user.is_verified,
        },
        "profile": {
            "first_name": user.profile.first_name if user.profile else "",
            "middle_name": user.profile.middle_name if user.profile else "",
            "last_name": user.profile.last_name if user.profile else "",
            "husband_surname": user.profile.husband_surname if user.profile else "",
            "country_residence": user.profile.country_residence if user.profile else "",
            "degree": user.profile.degree if user.profile else "",
            "year_graduated": user.profile.year_graduated if user.profile else "",
            "guardian_type": user.profile.guardian_type if user.profile else "",
        } if user.profile else None,
        "university_record": {
            "student_id": user.university_record.student_id,
            "first_name": user.university_record.first_name,
            "middle_name": user.university_record.middle_name,
            "last_name": user.university_record.last_name,
            "personal_email": user.university_record.personal_email,
            "degree": user.university_record.degree,
            "year_graduated": user.university_record.year_graduated,
            "college": user.university_record.college,
        } if user.university_record else None,
        "submission": {
            "id": latest.id,
            "submitted_at": latest.submitted_at,
            "alignment_status": latest.alignment_status,
            "data": latest.data_json,
            "extra_answers": latest.extra_answers,
        }
        if latest
        else None,
        "further_studies": [
            {
                "course_degree": s.course_degree,
                "school": s.school,
                "year_enrolled": s.year_enrolled,
                "scholarship": s.scholarship,
                "is_graduated": s.is_graduated,
            }
            for s in studies
        ],
        "resumes": [
            {"id": r.id, "filename": r.original_filename, "created_at": r.created_at, "parsed": r.parsed_json}
            for r in resumes
        ],
    }


@router.post("/approvals/{account_id}/verify")
def verify_graduate(account_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(Account, account_id)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")
    profile = user.profile
    record = None
    reason = "No graduate record match found"
    matched = False
    match_type = "none"
    if user.linked_student_id:
        record = db.get(UniversityRecord, user.linked_student_id)
        if record:
            matched, reason, match_type = True, f"Matched by Student ID ({record.student_id})", "student_id"
    if not matched:
        record = match_university_record(
            db,
            user.personal_email,
            profile.first_name if profile else "",
            profile.last_name if profile else "",
            profile.middle_name if profile else "",
        )
        if record:
            if student_id_in_use(db, record.student_id, exclude_account_id=user.id):
                return {
                    "matched": False,
                    "match_type": "already_linked",
                    "reason": "This graduate record is already linked to another account.",
                    "record": {
                        "student_id": record.student_id,
                        "first_name": record.first_name,
                        "middle_name": record.middle_name,
                        "last_name": record.last_name,
                        "email": record.personal_email,
                        "degree": record.degree,
                        "year_graduated": record.year_graduated,
                        "college": record.college,
                    },
                }
            if not user.linked_student_id:
                user.linked_student_id = record.student_id
                user.is_verified = True
                db.commit()
            matched = True
            match_type = "email_name"
            reason = f"Matched by email/name • Student ID {record.student_id}"
    return {
        "matched": matched,
        "match_type": match_type,
        "reason": reason,
        "record": {
            "student_id": record.student_id,
            "first_name": record.first_name,
            "middle_name": record.middle_name,
            "last_name": record.last_name,
            "email": record.personal_email,
            "degree": record.degree,
            "year_graduated": record.year_graduated,
            "college": record.college,
        }
        if record
        else None,
    }


@router.post("/approvals/{account_id}/approve")
def approve(account_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(Account, account_id)
    if not user or user.role != "Alumni":
        raise HTTPException(status_code=404, detail="Alumni account not found.")
    if user.status == "Active":
        if not user.is_verified:
            user.is_verified = True
            db.commit()
        return {"ok": True, "status": user.status, "already_processed": True}
    if user.status != "Pending":
        raise HTTPException(
            status_code=409,
            detail="This registration is no longer pending and cannot be approved.",
        )
    old = user.status
    user.status = "Active"
    user.is_verified = True
    _log(db, admin.id, "APPROVE", account_id, {"status": old}, {"status": "Active"})
    recipient = user.personal_email
    recipient_name = _account_name(user)
    db.commit()
    send_account_status_email(to_address=recipient, name=recipient_name, status="Active")
    return {"ok": True, "status": user.status}


@router.post("/approvals/{account_id}/reject")
def reject(account_id: int, payload: RejectRequest, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(Account, account_id)
    if not user or user.role != "Alumni":
        raise HTTPException(status_code=404, detail="Alumni account not found.")
    if user.status == "Rejected":
        return {"ok": True, "status": user.status, "already_processed": True}
    if user.status != "Pending":
        raise HTTPException(
            status_code=409,
            detail="This registration is no longer pending and cannot be rejected.",
        )
    old = user.status
    user.status = "Rejected"
    user.rejection_reason = payload.reason
    _log(db, admin.id, "REJECT", account_id, {"status": old}, {"status": "Rejected", "reason": payload.reason})
    recipient = user.personal_email
    recipient_name = _account_name(user)
    reason = payload.reason
    db.commit()
    send_account_status_email(
        to_address=recipient,
        name=recipient_name,
        status="Rejected",
        reason=reason,
    )
    return {"ok": True, "status": user.status}


@router.get("/resumes/{resume_id}/file")
def download_resume(resume_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(Resume, resume_id)
    if not row:
        raise HTTPException(status_code=404, detail="Resume not found.")
    path = resolve_stored_file(row.stored_path, missing_detail="Resume file is no longer on disk.")
    return FileResponse(path, filename=safe_download_name(row.original_filename))


@router.get("/academic-filters")
def academic_filters(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    return academic_catalog(db)


@router.get("/tracer")
def tracer_records(
    email: str = "",
    alignment: str = "All",
    college: str = "",
    course: str = "",
    page: int = 1,
    page_size: int = 20,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    page = max(1, page)
    page_size = min(50, max(5, page_size))
    q = db.query(TracerSubmission).join(Account, Account.id == TracerSubmission.account_id)
    if email.strip():
        q = q.filter(Account.personal_email.ilike(f"%{email.strip()}%"))
    if alignment and alignment != "All":
        q = q.filter(TracerSubmission.alignment_status == alignment)
    q = apply_tracer_academic_filters(q, college, course)
    total = q.count()
    rows = q.order_by(TracerSubmission.submitted_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for row in rows:
        items.append(_tracer_payload(row))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _tracer_payload(row: TracerSubmission) -> dict:
    data = row.data_json or {}
    current = resolve_current_employment(data)
    return {
        "id": row.id,
        "account_id": row.account_id,
        "email": row.account.personal_email if row.account else "",
        "student_id": row.student_id,
        "job_title": current.occupation,
        "employer": current.employer,
        "employment_status": data.get("is_currently_employed") or data.get("first_stat") or "",
        "alignment": row.alignment_status,
        "score": row.alignment_score,
        "submitted_at": row.submitted_at,
        "soc_code": row.soc_code or data.get("soc_code") or "",
        "soc_description": data.get("soc_description") or "",
        "soc_category": data.get("soc_category") or "",
        "data": data,
        "extra_answers": row.extra_answers,
        "survey_version": row.survey_version or data.get("_survey_version"),
    }


@router.get("/tracer/{submission_id}")
def tracer_record(submission_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    row = (
        db.query(TracerSubmission)
        .options(joinedload(TracerSubmission.account))
        .filter(TracerSubmission.id == submission_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Tracer record not found.")
    return _tracer_payload(row)


@router.get("/questions")
def list_questions(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    survey = ensure_gts_survey(db)
    db.commit()
    draft = survey.draft_schema or {}
    extras = extras_payload(draft)
    core_sections = []
    items = []
    for section, _sub, question in iter_questions(draft):
        is_extra = question.get("storage") == "extra"
        extra_id = question.get("extra_key") if is_extra else question.get("id")
        items.append(
            {
                "id": extra_id,
                "schema_id": question.get("id"),
                "section_key": section.get("key"),
                "label": question.get("label"),
                "input_type": question.get("type"),
                "options": question.get("options") or [],
                "required": bool(question.get("required")),
                "order_index": 0,
                "is_core": not is_extra,
                "active": True,
                "system": bool(question.get("system")),
            }
        )
    for section in draft.get("sections") or []:
        labels = [
            question.get("label")
            for sub in section.get("subsections") or []
            for question in sub.get("questions") or []
            if question.get("storage") != "extra"
        ]
        core_sections.append(
            {
                "key": section.get("key"),
                "name": section.get("name"),
                "locked": False,
                "fields": labels,
            }
        )
    return {
        "core_sections": core_sections or CORE_GTS_SECTIONS,
        "question_types": QUESTION_TYPES,
        "items": extras,
        "all_items": items,
    }


@router.post("/questions")
def create_question(payload: QuestionIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.input_type not in QUESTION_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported question type.")
    if not payload.label.strip():
        raise HTTPException(status_code=400, detail="Question title is required.")
    return add_legacy_extra(db, admin, payload)


@router.patch("/questions/{question_id}")
def update_question(question_id: int, payload: QuestionUpdate, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    survey = ensure_gts_survey(db)
    draft = clone_schema(survey.draft_schema)
    target = None
    for _section, _sub, question in iter_questions(draft):
        if str(question.get("extra_key") or "") == str(question_id) or question.get("id") == f"extra_{question_id}":
            target = question
            break
    if not target:
        raise HTTPException(status_code=404, detail="Question not found.")
    data = payload.model_dump(exclude_unset=True)
    if "label" in data and data["label"]:
        target["label"] = data["label"]
    if "input_type" in data and data["input_type"]:
        target["type"] = data["input_type"]
    if "options" in data and data["options"] is not None:
        target["options"] = data["options"]
    if "required" in data and data["required"] is not None:
        target["required"] = data["required"]
    if "section_key" in data and data["section_key"]:
        moved = target
        for section in draft.get("sections") or []:
            for sub in section.get("subsections") or []:
                sub["questions"] = [item for item in sub.get("questions") or [] if item.get("id") != moved.get("id")]
        dest = next((section for section in draft.get("sections") or [] if section.get("key") == data["section_key"]), None)
        if dest:
            dest.setdefault("subsections", [{"id": f"{dest['id']}_main", "name": "", "questions": []}])
            dest["subsections"][-1].setdefault("questions", []).append(moved)
    save_draft(db, admin, draft)
    _log(db, admin.id, "UPDATE_QUESTION", question_id, None, data)
    return {"ok": True}


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    delete_legacy_extra(db, admin, question_id)
    return {"ok": True}


@router.get("/soc")
def list_soc(
    q: str = "",
    page: int = 1,
    page_size: int = 25,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(SocCode)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                SocCode.description.ilike(like),
                SocCode.soc_code.ilike(like),
                SocCode.category.ilike(like),
                SocCode.title_patterns.ilike(like),
            )
        )
    page = max(1, page)
    page_size = min(100, max(5, page_size))
    total = query.count()
    rows = query.order_by(SocCode.soc_code).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "soc_code": r.soc_code,
                "code": r.code,
                "description": r.description,
                "category": r.category,
                "title_patterns": r.title_patterns,
                "degree_patterns": r.degree_patterns,
                "major_group": r.major_group,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/soc")
def create_soc(payload: SocIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    code = payload.soc_code.strip()
    if not code or not payload.description.strip():
        raise HTTPException(status_code=400, detail="SOC code and description are required.")
    if db.get(SocCode, code):
        raise HTTPException(status_code=400, detail="That SOC code already exists.")
    row = SocCode(
        soc_code=code,
        code=code,
        description=payload.description.strip(),
        category=payload.category,
        title_patterns=payload.title_patterns,
        degree_patterns=payload.degree_patterns,
        major_group=payload.major_group,
    )
    db.add(row)
    _log(db, admin.id, "CREATE_SOC", code, None, payload.model_dump())
    db.commit()
    invalidate_soc_cache()
    return {"ok": True, "soc_code": code}


@router.post("/job-mappings")
def create_mapping(payload: MappingIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    title = payload.raw_title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Job title is required.")
    if not db.get(SocCode, payload.soc_code):
        raise HTTPException(status_code=400, detail="Unknown SOC code.")
    existing = db.query(JobTitleMapping).filter(JobTitleMapping.raw_title == title).first()
    if existing:
        existing.soc_code = payload.soc_code
        existing.normalized_title = title.lower()
        existing.admin_notes = payload.admin_notes
        existing.last_modified_by = admin.id
        existing.approved = True
    else:
        db.add(
            JobTitleMapping(
                raw_title=title,
                normalized_title=title.lower(),
                soc_code=payload.soc_code,
                approved=True,
                admin_notes=payload.admin_notes,
                last_modified_by=admin.id,
            )
        )
    _log(db, admin.id, "MAP_JOB_TITLE", title, None, payload.model_dump())
    db.commit()
    return {"ok": True}


@router.get("/reports")
def reports(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    alumni = db.query(Account).filter(Account.role == "Alumni")
    by_status = {
        "Active": alumni.filter(Account.status == "Active").count(),
        "Pending": alumni.filter(Account.status == "Pending").count(),
        "Rejected": alumni.filter(Account.status == "Rejected").count(),
    }
    by_year = (
        db.query(AlumniProfile.year_graduated, func.count(AlumniProfile.id))
        .group_by(AlumniProfile.year_graduated)
        .order_by(AlumniProfile.year_graduated)
        .all()
    )
    latest_rows = latest_submissions(db)
    related = 0
    employed = 0
    for row in latest_rows:
        data = row.data_json or {}
        if data.get("is_currently_employed") == "Yes":
            employed += 1
        if _relatedness(data, row.alignment_status or "") == "related":
            related += 1
    return {
        "registered": alumni.count(),
        "approved": by_status["Active"],
        "pending": by_status["Pending"],
        "rejected": by_status["Rejected"],
        "by_status": by_status,
        "by_graduation_year": [{"year": y or "Unknown", "count": c} for y, c in by_year],
        "currently_employed_submissions": employed,
        "degree_related_submissions": related,
        "alumni_with_submissions": len(latest_rows),
        "total_submissions": db.query(TracerSubmission).count(),
        "options": filter_options(db),
    }


@router.get("/reports/employment")
def employment_report(
    college: str = "",
    program: str = "",
    course: str = "",
    year: str = "",
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return employment_analytics(db, college=college, program=program or course, year=year)


def _oaaps_filters(
    college: str = "",
    program: str = "",
    year: str = "",
    period_from: str = "",
    period_to: str = "",
):
    try:
        submitted_from = parse_report_date(period_from)
        submitted_to = parse_report_date(period_to, end_of_day=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Reporting period dates must use YYYY-MM-DD.") from exc
    if submitted_from and submitted_to and submitted_from > submitted_to:
        raise HTTPException(status_code=400, detail="Reporting period start date must be on or before the end date.")
    return {
        "college": college,
        "program": program,
        "year": year,
        "period_from": period_from,
        "period_to": period_to,
        "submitted_from": submitted_from,
        "submitted_to": submitted_to,
    }


@router.get("/reports/oaaps")
def oaaps_reports(
    college: str = "",
    program: str = "",
    year: str = "",
    period_from: str = "",
    period_to: str = "",
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return build_oaaps_report(db, **_oaaps_filters(college, program, year, period_from, period_to))


@router.get("/reports/oaaps/export")
def export_oaaps_report(
    college: str = "",
    program: str = "",
    year: str = "",
    period_from: str = "",
    period_to: str = "",
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    report = build_oaaps_report(db, **_oaaps_filters(college, program, year, period_from, period_to))
    payload = render_oaaps_docx(report)
    filename = f"AUF-OAAPS-Graduate-Productivity-Report-{datetime.now().strftime('%Y%m%d')}.docx"
    return StreamingResponse(
        iter([payload]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/export")
def export_reports(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "email",
            "student_id",
            "name",
            "degree",
            "year_graduated",
            "status",
            "job_title",
            "employer",
            "alignment",
            "submitted_at",
        ]
    )
    rows = latest_submissions(db)
    for row in rows:
        data = row.data_json or {}
        writer.writerow(
            [
                csv_safe(row.account.personal_email if row.account else ""),
                csv_safe(row.student_id or ""),
                csv_safe(
                    " ".join(
                        p
                        for p in [
                            data.get("first_name"),
                            data.get("middle_name"),
                            data.get("last_name"),
                        ]
                        if p
                    )
                ),
                csv_safe(data.get("degree", "")),
                csv_safe(data.get("year_graduated", "")),
                csv_safe(row.account.status if row.account else ""),
                csv_safe(resolve_current_employment(data).occupation),
                csv_safe(resolve_current_employment(data).employer),
                csv_safe(row.alignment_status),
                csv_safe(row.submitted_at.isoformat() if row.submitted_at else ""),
            ]
        )
    output.seek(0)
    filename = f"careersense-tracer-{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/university-records")
def list_university_records(
    q: str = "",
    college: str = "",
    course: str = "",
    page: int = 1,
    page_size: int = 25,
    admin: Account = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(UniversityRecord)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                UniversityRecord.student_id.ilike(like),
                UniversityRecord.personal_email.ilike(like),
                UniversityRecord.first_name.ilike(like),
                UniversityRecord.last_name.ilike(like),
            )
        )
    query = apply_registry_academic_filters(query, college, course)
    page = max(1, page)
    page_size = min(100, max(5, page_size))
    total = query.count()
    rows = query.order_by(
        UniversityRecord.year_graduated.desc(), UniversityRecord.last_name
    ).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "student_id": r.student_id,
                "first_name": r.first_name,
                "middle_name": r.middle_name,
                "last_name": r.last_name,
                "personal_email": r.personal_email,
                "degree": r.degree,
                "year_graduated": r.year_graduated,
                "course_code": r.course_code,
                "college": r.college,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/university-records")
def create_university_record(payload: UniversityRecordIn, admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    if db.get(UniversityRecord, payload.student_id.strip()):
        raise HTTPException(status_code=400, detail="Student ID already exists.")
    email = str(payload.personal_email).strip().lower()
    if db.query(UniversityRecord).filter(UniversityRecord.personal_email == email).first():
        raise HTTPException(status_code=400, detail="A graduate record already uses this email.")
    row = UniversityRecord(
        student_id=payload.student_id.strip(),
        first_name=payload.first_name.strip(),
        middle_name=payload.middle_name.strip(),
        last_name=payload.last_name.strip(),
        personal_email=email,
        degree=payload.degree.strip(),
        year_graduated=payload.year_graduated.strip(),
        course_code=payload.course_code.strip(),
        college=payload.college.strip(),
    )
    db.add(row)
    _log(db, admin.id, "CREATE_UNIVERSITY_RECORD", row.student_id, None, payload.model_dump())
    db.commit()
    return {"ok": True, "student_id": row.student_id}


@router.get("/logs")
def logs(admin: Account = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "admin_id": r.admin_id,
            "action_type": r.action_type,
            "target_id": r.target_id,
            "new_value": r.new_value,
            "created_at": r.created_at,
        }
        for r in rows
    ]

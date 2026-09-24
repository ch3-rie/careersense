from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


class UniversityRecord(Base):
    __tablename__ = "university_records"

    student_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    middle_name: Mapped[str] = mapped_column(String(80), default="")
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    personal_email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    degree: Mapped[str] = mapped_column(String(200), nullable=False)
    year_graduated: Mapped[str] = mapped_column(String(8), nullable=False)
    course_code: Mapped[str] = mapped_column(String(40), default="")
    college: Mapped[str] = mapped_column(String(160), default="")

    accounts: Mapped[list["Account"]] = relationship(back_populates="university_record")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    personal_email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    linked_student_id: Mapped[Optional[str]] = mapped_column(
        String(40),
        ForeignKey("university_records.student_id"),
        nullable=True,
        unique=True,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="Pending", index=True)
    role: Mapped[str] = mapped_column(String(20), default="Alumni", index=True)
    rejection_reason: Mapped[str] = mapped_column(Text, default="")
    privacy_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_name: Mapped[str] = mapped_column(String(80), default="")
    last_name: Mapped[str] = mapped_column(String(80), default="")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    university_record: Mapped[Optional[UniversityRecord]] = relationship(back_populates="accounts")
    profile: Mapped[Optional["AlumniProfile"]] = relationship(back_populates="account", uselist=False)
    submissions: Mapped[list["TracerSubmission"]] = relationship(back_populates="account")
    resumes: Mapped[list["Resume"]] = relationship(back_populates="account")
    skills: Mapped[list["AlumniSkill"]] = relationship(back_populates="account")
    studies: Mapped[list["FurtherStudy"]] = relationship(back_populates="account")
    jobs: Mapped[list["AlumniJob"]] = relationship(back_populates="account")
    alignment: Mapped[Optional["AlignmentResult"]] = relationship(back_populates="account", uselist=False)
    alumni_card: Mapped[Optional["AlumniCard"]] = relationship(back_populates="account", uselist=False)
    notifications: Mapped[list["AlumniNotification"]] = relationship(back_populates="account")
    badges: Mapped[list["AlumniBadge"]] = relationship(back_populates="account")
    perk_redemptions: Mapped[list["AlumniPerkRedemption"]] = relationship(back_populates="account")
    password_resets: Mapped[list["PasswordResetVerification"]] = relationship(back_populates="account")
    admin_logs: Mapped[list["AdminLog"]] = relationship(
        back_populates="admin", foreign_keys="AdminLog.admin_id"
    )


class AlumniProfile(Base):
    __tablename__ = "alumni_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), default="")
    middle_name: Mapped[str] = mapped_column(String(80), default="")
    last_name: Mapped[str] = mapped_column(String(80), default="")
    husband_surname: Mapped[str] = mapped_column(String(80), default="")
    country_residence: Mapped[str] = mapped_column(String(80), default="Philippines")
    degree: Mapped[str] = mapped_column(String(200), default="")
    year_graduated: Mapped[str] = mapped_column(String(8), default="")
    guardian_type: Mapped[str] = mapped_column(String(80), default="")
    guardian_degree_completed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    job_timeline_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    phone: Mapped[str] = mapped_column(String(40), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    photo_path: Mapped[str] = mapped_column(String(500), default="")
    photo_mime: Mapped[str] = mapped_column(String(120), default="")
    cover_path: Mapped[str] = mapped_column(String(500), default="")
    cover_mime: Mapped[str] = mapped_column(String(120), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    address: Mapped[str] = mapped_column(String(240), default="")
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped[Account] = relationship(back_populates="profile")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), default="application/pdf")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    parsed_json: Mapped[dict] = mapped_column(JSON, default=dict)
    parser_source: Mapped[str] = mapped_column(String(40), default="heuristic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped[Account] = relationship(back_populates="resumes")


class RegistrationDraft(Base):
    """Temporary registration state. No alumni account exists until the GTS is submitted."""

    __tablename__ = "registration_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    personal_email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    linked_student_id: Mapped[Optional[str]] = mapped_column(
        String(40), ForeignKey("university_records.student_id"), nullable=True
    )
    privacy_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), default="application/pdf")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    parsed_json: Mapped[dict] = mapped_column(JSON, default=dict)
    parser_source: Mapped[str] = mapped_column(String(40), default="heuristic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TracerSubmission(Base):
    __tablename__ = "tracer_submissions"
    __table_args__ = (Index("ix_tracer_account_submitted", "account_id", "submitted_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    student_id: Mapped[Optional[str]] = mapped_column(
        String(40), ForeignKey("university_records.student_id"), nullable=True
    )
    resume_id: Mapped[Optional[int]] = mapped_column(ForeignKey("resumes.id"), nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    extra_answers: Mapped[dict] = mapped_column(JSON, default=dict)
    survey_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    alignment_status: Mapped[str] = mapped_column(String(20), default="Unknown")
    alignment_score: Mapped[int] = mapped_column(Integer, default=50)
    soc_code: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("soc_codes.soc_code"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped[Account] = relationship(back_populates="submissions")


class FurtherStudy(Base):
    __tablename__ = "further_studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    course_degree: Mapped[str] = mapped_column(String(200), default="")
    school: Mapped[str] = mapped_column(String(200), default="")
    year_enrolled: Mapped[str] = mapped_column(String(8), default="")
    scholarship: Mapped[str] = mapped_column(String(200), default="")
    is_graduated: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    account: Mapped[Account] = relationship(back_populates="studies")


class AlumniJob(Base):
    __tablename__ = "alumni_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    job_title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    industry: Mapped[str] = mapped_column(String(120), default="")
    location: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")

    account: Mapped[Account] = relationship(back_populates="jobs")


class AlumniSkill(Base):
    __tablename__ = "alumni_skills"
    __table_args__ = (UniqueConstraint("account_id", "skill_name", name="uq_account_skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="")

    account: Mapped[Account] = relationship(back_populates="skills")


class AlignmentResult(Base):
    __tablename__ = "alignment_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True, nullable=False)
    overall_match_score: Mapped[int] = mapped_column(Integer, default=50)
    alignment_justification: Mapped[str] = mapped_column(String(40), default="Unknown")
    justification_detail: Mapped[str] = mapped_column(Text, default="")
    suggested_career_paths: Mapped[list] = mapped_column(JSON, default=list)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped[Account] = relationship(back_populates="alignment")


class SocCode(Base):
    __tablename__ = "soc_codes"

    soc_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    title_patterns: Mapped[str] = mapped_column(Text, default="")
    degree_patterns: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(120), default="")
    major_group: Mapped[str] = mapped_column(String(80), default="")


class JobTitleMapping(Base):
    __tablename__ = "job_title_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_title: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(200), default="")
    soc_code: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("soc_codes.soc_code"), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    admin_notes: Mapped[str] = mapped_column(Text, default="")
    last_modified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True)


class GtsQuestion(Base):
    __tablename__ = "gts_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(400), nullable=False)
    input_type: Mapped[str] = mapped_column(String(40), nullable=False)
    options: Mapped[list] = mapped_column(JSON, default=list)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_core: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(80), default="")
    old_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    admin: Mapped[Optional[Account]] = relationship(foreign_keys=[admin_id], back_populates="admin_logs")


class AacAppointmentSlot(Base):
    """OAAPS-published AAC appointment capacity. Alumni only see slots that still have room."""

    __tablename__ = "aac_appointment_slots"
    __table_args__ = (
        UniqueConstraint("slot_date", "slot_time", name="uq_aac_slot_date_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    slot_time: Mapped[str] = mapped_column(String(8), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=8)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AlumniCard(Base):
    __tablename__ = "alumni_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="NotYetApplied", index=True)
    card_number: Mapped[str] = mapped_column(String(40), default="")
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_location: Mapped[str] = mapped_column(String(200), default="AAPS, AUF Main Campus")
    application_json: Mapped[dict] = mapped_column(JSON, default=dict)

    account: Mapped[Account] = relationship(back_populates="alumni_card")


class AlumniNotification(Base):
    __tablename__ = "alumni_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40), default="announcement")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    link: Mapped[str] = mapped_column(String(200), default="")

    account: Mapped[Account] = relationship(back_populates="notifications")


class AlumniBadge(Base):
    """Persisted alumni achievements. Definitions live in the achievement catalog."""

    __tablename__ = "alumni_badges"
    __table_args__ = (
        UniqueConstraint("account_id", "badge_key", name="uq_alumni_badge_account_key"),
        Index("ix_alumni_badges_account_id", "account_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    badge_key: Mapped[str] = mapped_column(String(80), nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    award_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    account: Mapped[Account] = relationship(back_populates="badges")


class AlumniPerk(Base):
    __tablename__ = "alumni_perks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    discount: Mapped[str] = mapped_column(String(80), default="")
    how_to_claim: Mapped[str] = mapped_column(Text, default="")
    partner: Mapped[str] = mapped_column(String(160), default="")
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    requires_active_card: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(String(80), default="")
    eligibility: Mapped[str] = mapped_column(Text, default="")
    contact: Mapped[str] = mapped_column(String(255), default="")
    website: Mapped[str] = mapped_column(String(500), default="")
    image_path: Mapped[str] = mapped_column(String(500), default="")
    image_mime: Mapped[str] = mapped_column(String(120), default="")


class AlumniPerkRedemption(Base):
    __tablename__ = "alumni_perk_redemptions"
    __table_args__ = (UniqueConstraint("account_id", "perk_id", name="uq_account_perk"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    perk_id: Mapped[int] = mapped_column(ForeignKey("alumni_perks.id"), nullable=False, index=True)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    code: Mapped[str] = mapped_column(String(40), default="")

    account: Mapped[Account] = relationship(back_populates="perk_redemptions")
    perk: Mapped[AlumniPerk] = relationship()


class SurveyDefinition(Base):
    __tablename__ = "survey_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, default="gts")
    draft_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    published_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    published_version: Mapped[int] = mapped_column(Integer, default=0)
    draft_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    dirty: Mapped[bool] = mapped_column(Boolean, default=False)

    publisher: Mapped[Optional[Account]] = relationship(foreign_keys=[published_by_id])
    versions: Mapped[list["SurveyVersion"]] = relationship(back_populates="survey")


class SurveyVersion(Base):
    __tablename__ = "survey_versions"
    __table_args__ = (UniqueConstraint("survey_id", "version_number", name="uq_survey_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("survey_definitions.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True)

    survey: Mapped[SurveyDefinition] = relationship(back_populates="versions")
    publisher: Mapped[Optional[Account]] = relationship(foreign_keys=[published_by_id])


class AlumniCertification(Base):
    __tablename__ = "alumni_certifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    certification_name: Mapped[str] = mapped_column(String(200), nullable=False)
    issuing_organization: Mapped[str] = mapped_column(String(200), default="")
    date_issued: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    skills_covered: Mapped[list] = mapped_column(JSON, default=list)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class ProfileUpdateRequest(Base):
    __tablename__ = "profile_update_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    requested_fields: Mapped[list] = mapped_column(JSON, default=list)
    other_detail: Mapped[str] = mapped_column(String(400), default="")
    target_route: Mapped[str] = mapped_column(String(80), default="/alumni")
    status: Mapped[str] = mapped_column(String(40), default="Sent", index=True)
    email_sent_count: Mapped[int] = mapped_column(Integer, default=0)
    email_failed_count: Mapped[int] = mapped_column(Integer, default=0)
    recipient_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    admin: Mapped[Optional[Account]] = relationship(foreign_keys=[created_by])
    recipients: Mapped[list["ProfileUpdateRequestRecipient"]] = relationship(back_populates="request")


class ProfileUpdateRequestRecipient(Base):
    __tablename__ = "profile_update_request_recipients"
    __table_args__ = (UniqueConstraint("request_id", "alumni_id", name="uq_profile_update_recipient"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("profile_update_requests.id"), nullable=False, index=True)
    alumni_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    notification_id: Mapped[Optional[int]] = mapped_column(ForeignKey("alumni_notifications.id"), nullable=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    email_status: Mapped[str] = mapped_column(String(20), default="failed")
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    email_error: Mapped[str] = mapped_column(String(400), default="")
    viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_json: Mapped[dict] = mapped_column(JSON, default=dict)

    request: Mapped[ProfileUpdateRequest] = relationship(back_populates="recipients")
    alumni: Mapped[Optional[Account]] = relationship(foreign_keys=[alumni_id])


class PasswordResetVerification(Base):
    """Hashed email PIN and one-time reset authorization. Raw PINs and tokens are never stored."""

    __tablename__ = "password_reset_verifications"
    __table_args__ = (
        Index("ix_pwreset_email_created", "email_hash", "created_at"),
        Index("ix_pwreset_reset_token", "reset_token_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    pin_hash: Mapped[str] = mapped_column(String(160), nullable=False)
    reset_token_hash: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reset_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped[Optional[Account]] = relationship(back_populates="password_resets")


class EmailOutbox(Base):
    """Retry queue for non-secret transactional mail. PIN and password-reset bodies are never stored."""

    __tablename__ = "email_outbox"
    __table_args__ = (Index("ix_email_outbox_status_retry", "status", "next_retry_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    to_address: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    text_body: Mapped[str] = mapped_column(Text, default="")
    html_body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    last_error: Mapped[str] = mapped_column(String(400), default="")
    provider: Mapped[str] = mapped_column(String(40), default="")
    provider_message_id: Mapped[str] = mapped_column(String(120), default="")
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileReminderSettings(Base):
    """Singleton admin configuration for automated profile-update reminder emails."""

    __tablename__ = "profile_reminder_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    frequency: Mapped[str] = mapped_column(String(20), default="weekly")
    interval_days: Mapped[int] = mapped_column(Integer, default=14)
    send_hour: Mapped[int] = mapped_column(Integer, default=9)
    send_weekday: Mapped[int] = mapped_column(Integer, default=0)
    send_day_of_month: Mapped[int] = mapped_column(Integer, default=1)
    target_mode: Mapped[str] = mapped_column(String(20), default="incomplete")
    target_filters: Mapped[dict] = mapped_column(JSON, default=dict)
    alumni_ids: Mapped[list] = mapped_column(JSON, default=list)
    subject: Mapped[str] = mapped_column(String(200), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    requested_fields: Mapped[list] = mapped_column(JSON, default=list)
    other_detail: Mapped[str] = mapped_column(String(400), default="")
    min_days_between: Mapped[int] = mapped_column(Integer, default=14)
    skip_if_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scheduled_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProfileReminderRun(Base):
    __tablename__ = "profile_reminder_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    triggered_by: Mapped[str] = mapped_column(String(20), default="schedule")
    admin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    disabled_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(400), default="")
    settings_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    sends: Mapped[list["ProfileReminderSend"]] = relationship(back_populates="run")


class ProfileReminderSend(Base):
    __tablename__ = "profile_reminder_sends"
    __table_args__ = (Index("ix_profile_reminder_sends_alumni_sent", "alumni_id", "sent_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("profile_reminder_runs.id"), nullable=False, index=True)
    alumni_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    email_status: Mapped[str] = mapped_column(String(20), default="skipped")
    email_error: Mapped[str] = mapped_column(String(400), default="")
    skipped_reason: Mapped[str] = mapped_column(String(80), default="")
    notification_id: Mapped[Optional[int]] = mapped_column(ForeignKey("alumni_notifications.id"), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[ProfileReminderRun] = relationship(back_populates="sends")
    alumni: Mapped[Optional[Account]] = relationship(foreign_keys=[alumni_id])

import re
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    personal_email: str
    role: str
    status: str
    linked_student_id: Optional[str] = None
    is_verified: bool = False
    rejection_reason: str = ""
    created_at: Optional[datetime] = None
    first_name: str = ""
    last_name: str = ""
    must_change_password: bool = False
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_validator("must_change_password", mode="before")
    @classmethod
    def _coerce_flag(cls, value):
        return bool(value)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _coerce_name(cls, value):
        return value or ""


class ProfileOut(BaseModel):
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    husband_surname: str = ""
    country_residence: str = "Philippines"
    degree: str = ""
    year_graduated: str = ""
    guardian_type: str = ""
    guardian_degree_completed: Optional[bool] = None

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    matched_record: Optional[dict[str, Any]] = None
    parsed_resume: dict[str, Any] = Field(default_factory=dict)
    gts_prefill: dict[str, Any] = Field(default_factory=dict)
    parser_source: str = "heuristic"


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordVerifyRequest(BaseModel):
    email: str
    pin: str


class ForgotPasswordResendRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str


class FurtherStudyIn(BaseModel):
    course_degree: str = ""
    school: str = ""
    year_enrolled: str = ""
    scholarship: str = ""
    is_graduated: Optional[str] = "No"


class GtsPayload(BaseModel):
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    husband_surname: str = ""
    country: str = "Philippines"
    degree: str = ""
    year_graduated: str = ""
    primary_guardian: Optional[str] = None
    guardian_degree_completed: Optional[str] = None
    ever_employed: Optional[str] = None
    time_to_first_job: Optional[str] = None
    first_related: Optional[str] = None
    find_job: Optional[str] = None
    other_find_job: str = ""
    is_currently_employed: Optional[str] = None
    present_job_is_first: Optional[str] = None
    reason_past: list[str] = Field(default_factory=list)
    reason_past_other: str = ""
    reason_current: list[str] = Field(default_factory=list)
    reason_current_other: str = ""
    first_occ: str = ""
    first_emp: str = ""
    first_sal: str = ""
    first_stat: str = ""
    pres_occ: str = ""
    pres_emp: str = ""
    pres_head: str = ""
    pres_head_email: str = ""
    pres_stay: str = ""
    present_related_degree: Optional[str] = None
    enroll_further_studies: str = "No"
    further_studies: list[dict[str, Any]] = Field(default_factory=list)
    participated_seminars: Optional[str] = None
    seminars_helpful: Optional[str] = None
    mentoring_rating: Optional[int] = None
    advocacy_rating: Optional[int] = None
    volunteering_rating: Optional[int] = None
    engagement_desc: str = ""
    curriculum_suggestions: dict[str, Any] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    extra_answers: dict[str, Any] = Field(default_factory=dict)
    resume_id: Optional[int] = None
    registration_token: Optional[str] = None


class QuestionIn(BaseModel):
    section_key: str
    label: str
    input_type: str
    options: list[str] = Field(default_factory=list)
    required: bool = False
    order_index: int = 0


class QuestionUpdate(BaseModel):
    label: Optional[str] = None
    input_type: Optional[str] = None
    options: Optional[list[str]] = None
    required: Optional[bool] = None
    order_index: Optional[int] = None
    active: Optional[bool] = None
    section_key: Optional[str] = None


class SocIn(BaseModel):
    soc_code: str
    description: str
    category: str = ""
    title_patterns: str = ""
    degree_patterns: str = ""
    major_group: str = ""


class UniversityRecordIn(BaseModel):
    student_id: str
    first_name: str
    middle_name: str = ""
    last_name: str
    personal_email: EmailStr
    degree: str
    year_graduated: str
    course_code: str = ""
    college: str = ""


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3)


class MappingIn(BaseModel):
    raw_title: str
    soc_code: str
    admin_notes: str = ""


class JobIn(BaseModel):
    job_title: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool = False
    industry: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=800)


class StudyIn(BaseModel):
    course_degree: str = Field(min_length=1, max_length=200)
    school: str = Field(min_length=1, max_length=200)
    year_enrolled: str = Field(default="", max_length=8)
    scholarship: str = Field(default="", max_length=200)
    is_graduated: Optional[bool] = None


class ProfileUpdateIn(BaseModel):
    country_residence: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=40)
    city: str = Field(default="", max_length=120)
    address: str = Field(default="", max_length=240)
    husband_surname: str = Field(default="", max_length=80)
    bio: str = Field(default="", max_length=800)


MEMBERSHIP_TYPES = ("New", "Renewal", "Regular", "Lifetime", "Replacement")


class CardApplicationIn(BaseModel):
    birthday: date
    phone: str = Field(min_length=7, max_length=40)
    mailing_address: str = Field(min_length=8, max_length=240)
    city: str = Field(default="", max_length=120)
    country_residence: str = Field(default="Philippines", max_length=80)
    company_affiliation: str = Field(default="", max_length=200)
    position: str = Field(default="", max_length=200)
    membership_type: str = Field(default="New", min_length=3, max_length=40)
    pickup_acknowledged: bool = False
    appointment_date: date
    appointment_time: str = Field(min_length=4, max_length=8)

    @field_validator("membership_type")
    @classmethod
    def valid_membership(cls, value: str) -> str:
        if value not in MEMBERSHIP_TYPES:
            raise ValueError("Select New, Renewal, Regular, Lifetime, or Replacement.")
        return value

    @field_validator("appointment_time")
    @classmethod
    def valid_time(cls, value: str) -> str:
        cleaned = value.strip()
        if not re.fullmatch(r"\d{2}:\d{2}", cleaned):
            raise ValueError("Select an available appointment time.")
        return cleaned


class AppointmentSlotIn(BaseModel):
    slot_date: date
    slot_time: str = Field(min_length=4, max_length=8)
    capacity: int = Field(default=8, ge=1, le=100)

    @field_validator("slot_time")
    @classmethod
    def valid_slot_time(cls, value: str) -> str:
        cleaned = value.strip()
        if not re.fullmatch(r"\d{2}:\d{2}", cleaned):
            raise ValueError("Use a time like 09:00.")
        return cleaned


class CardStatusIn(BaseModel):
    status: str = Field(min_length=3, max_length=40)
    pickup_location: str = Field(default="", max_length=200)
    card_number: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=400)


class SurveyDraftIn(BaseModel):
    survey_schema: dict[str, Any] = Field(alias="schema")
    auto: bool = False

    model_config = {"populate_by_name": True}


class SurveySettingsIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    intro: Optional[str] = None
    confirmation_message: Optional[str] = None
    accepting_responses: Optional[bool] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    allow_alumni_edit: Optional[bool] = None


class SurveyPublishIn(BaseModel):
    confirm_impact: bool = False


class PerkIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    partner: str = Field(default="", max_length=160)
    category: str = Field(default="", max_length=80)
    description: str = ""
    discount: str = Field(default="", max_length=80)
    how_to_claim: str = ""
    eligibility: str = ""
    contact: str = Field(default="", max_length=255)
    website: str = Field(default="", max_length=500)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    requires_active_card: bool = False
    active: bool = True


class AdminUserCreateIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    role: str = "Admin"
    status: str = "Active"
    confirm: bool = False


class AdminUserUpdateIn(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=80)
    last_name: Optional[str] = Field(default=None, max_length=80)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    status: Optional[str] = None


class ProfileUpdateRequestIn(BaseModel):
    alumni_ids: list[int] = Field(min_length=1, max_length=200)
    requested_fields: list[str] = Field(min_length=1)
    other_detail: str = ""
    subject: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=10, max_length=2000)
    target: str = ""
    force_resend: bool = False


class ProfileReminderSettingsIn(BaseModel):
    enabled: bool = False
    frequency: str = "weekly"
    interval_days: int = 14
    send_hour: int = 9
    send_weekday: int = 0
    send_day_of_month: int = 1
    target_mode: str = "incomplete"
    target_year: str = ""
    target_degree: str = ""
    target_completion: str = ""
    alumni_ids: list[int] = Field(default_factory=list)
    requested_fields: list[str] = Field(min_length=1)
    other_detail: str = ""
    subject: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=10, max_length=2000)
    min_days_between: int = 14
    skip_if_complete: bool = True


class ProfileReminderRunIn(BaseModel):
    force: bool = False


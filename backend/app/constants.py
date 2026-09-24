SALARY_OPTIONS = [
    "Below ₱13,800",
    "₱13,800 to ₱27,599",
    "₱27,600 to ₱41,399",
    "₱41,400 to ₱55,199",
    "₱55,200 to ₱68,999",
    "₱69,000 and above",
]

EMPLOYMENT_STATUS_OPTIONS = [
    "Regular/Permanent",
    "Probationary",
    "Contractual/Casual",
    "Self-Employed",
]

TIME_TO_FIRST_JOB_OPTIONS = [
    "Less than a month",
    "1 to 6 months",
    "7 to 11 months",
    "1 year to less than 2 years",
    "2 years to less than 3 years",
    "3 years or more",
]

UNEMPLOYMENT_REASONS = [
    "Apprenticeship/Volunteer Work",
    "Family-related reason/s",
    "Board or Licensure Examination Preparation",
    "Health-related reason/s",
    "Looking for a job, but cannot find one",
    "Continuing Education",
    "Other",
]

HOW_FOUND_FIRST_JOB = [
    "Response to an advertisement",
    "As walk-in applicant",
    "Recommended by someone",
    "Information from friends",
    "Family business",
    "Arranged by AUF",
    "Public Employment Service Office / Job Fair",
    "Other",
]

GUARDIAN_OPTIONS = ["Both Parents", "Father", "Mother", "Other"]

QUESTION_TYPES = {
    "short_answer": "Short Answer",
    "paragraph": "Paragraph",
    "multiple_choice": "Multiple Choice",
    "checkboxes": "Checkboxes",
    "dropdown": "Dropdown",
    "scale": "Linear Scale",
    "yes_no": "Yes/No",
    "date": "Date",
    "number": "Number",
}

CORE_GTS_SECTIONS = [
    {
        "key": "general",
        "name": "General Information",
        "locked": True,
        "fields": [
            "Given Name, Middle Name, Last Name, Husband's Surname",
            "Personal Email",
            "Country of Residence",
            "Bachelor's Degree Earned",
            "Year Graduated",
            "Primary guardian/s",
            "Guardian college completion",
        ],
    },
    {
        "key": "employment",
        "name": "Employment Details",
        "locked": True,
        "fields": [
            "Ever employed after graduation",
            "Time to first job",
            "First job relatedness to degree",
            "How first job was found",
            "First job title, employer, salary, status",
            "Current employment status",
            "Present job details and relatedness",
        ],
    },
    {
        "key": "studies",
        "name": "Further Studies",
        "locked": True,
        "fields": [
            "Enrolled in further studies",
            "Course/Degree, School, Year, Scholarship, Graduated",
        ],
    },
    {
        "key": "feedback",
        "name": "Institutional Feedback",
        "locked": True,
        "fields": [
            "Career development seminar participation",
            "AUF inspiration ratings (mentoring, advocacy, volunteering)",
            "Engagement impact description",
            "Curriculum improvement suggestions",
        ],
    },
]

PRIVACY_NOTICE = (
    "By continuing, you consent to the collection and processing of your personal data "
    "by the Angeles University Foundation Office of Alumni Affairs and Placement Services "
    "for graduate tracer, alumni records, and institutional research purposes, in accordance "
    "with the Data Privacy Act of 2012 (RA 10173)."
)

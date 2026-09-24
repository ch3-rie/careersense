from app.services.employment import infer_present_job_is_first, resolve_current_employment


def test_present_is_first_uses_first_occupation():
    current = resolve_current_employment(
        {
            "is_currently_employed": "Yes",
            "present_job_is_first": "Yes",
            "first_occ": "Software Developer",
            "first_emp": "ABC",
            "pres_occ": "",
            "pres_emp": "",
        }
    )
    assert current.occupation == "Software Developer"
    assert current.employer == "ABC"
    assert current.present_is_first is True


def test_present_is_first_ignores_hidden_present_occupation():
    current = resolve_current_employment(
        {
            "is_currently_employed": "Yes",
            "present_job_is_first": "Yes",
            "first_occ": "Software Developer",
            "first_emp": "ABC",
            "pres_occ": "Systems Analyst",
            "pres_emp": "Hidden Corp",
        }
    )
    assert current.occupation == "Software Developer"
    assert current.employer == "ABC"


def test_present_is_not_first_uses_present_occupation():
    current = resolve_current_employment(
        {
            "is_currently_employed": "Yes",
            "present_job_is_first": "No",
            "first_occ": "IT Support Specialist",
            "first_emp": "Helpdesk Inc",
            "pres_occ": "Systems Analyst",
            "pres_emp": "ABC",
        }
    )
    assert current.occupation == "Systems Analyst"
    assert current.employer == "ABC"
    assert current.present_is_first is False


def test_unemployed_has_no_current_occupation():
    current = resolve_current_employment(
        {
            "is_currently_employed": "No",
            "present_job_is_first": "Yes",
            "first_occ": "Software Developer",
            "first_emp": "ABC",
        }
    )
    assert current.currently_employed is False
    assert current.occupation == ""
    assert current.employer == ""


def test_missing_occupation_is_not_fabricated():
    current = resolve_current_employment(
        {
            "is_currently_employed": "Yes",
            "present_job_is_first": "Yes",
            "first_occ": "",
            "first_emp": "",
            "pres_occ": "Systems Analyst",
            "pres_emp": "Hidden Corp",
        }
    )
    assert current.occupation == ""
    assert current.employer == ""


def test_same_employer_different_titles_are_separate_jobs():
    flag = infer_present_job_is_first(
        {"job_title": "Software Developer", "employer": "ABC Corporation"},
        {"job_title": "Systems Analyst", "employer": "ABC Corporation"},
    )
    assert flag == "No"


def test_single_current_role_is_first_job():
    job = {"job_title": "Software Engineer", "employer": "Acme"}
    assert infer_present_job_is_first(job, job) == "Yes"

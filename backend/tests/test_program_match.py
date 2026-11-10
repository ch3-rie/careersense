from tests.conftest import auth_header, login

from app.services.program_match import ProgramIndex

PROGRAMS = [
    {
        "college": "College of Computer Studies",
        "course": "BS Computer Science",
        "course_code": "BSCS",
        "kind": "undergraduate",
    },
    {
        "college": "College of Computer Studies",
        "course": "Bachelor of Science in Information Technology",
        "course_code": "BSIT",
        "kind": "undergraduate",
    },
    {
        "college": "College of Engineering and Architecture",
        "course": "BS Civil Engineering",
        "course_code": "BSCE",
        "kind": "undergraduate",
    },
    {
        "college": "College of Engineering and Architecture",
        "course": "BS Computer Engineering",
        "course_code": "BSCPE",
        "kind": "undergraduate",
    },
    {
        "college": "College of Nursing",
        "course": "BS Nursing",
        "course_code": "BSN",
        "kind": "undergraduate",
    },
]


def names(term: str) -> list[str]:
    found = ProgramIndex(PROGRAMS).programs_for_term(term)
    return sorted({item["course"] for item in found})


def test_abbreviation_matches_the_full_program_name():
    assert names("BS CS") == ["BS Computer Science"]
    assert names("  bs   cs ") == ["BS Computer Science"]
    assert names("BSCS") == ["BS Computer Science"]
    assert names("BS IT") == ["Bachelor of Science in Information Technology"]
    assert names("it") == ["Bachelor of Science in Information Technology"]


def test_partial_name_and_code_matches_stay_relevant():
    assert names("computer") == ["BS Computer Engineering", "BS Computer Science"]
    assert names("Comp Sci") == ["BS Computer Science"]
    assert names("BSC") == ["BS Civil Engineering", "BS Computer Engineering", "BS Computer Science"]
    assert names("nurs") == ["BS Nursing"]


def test_ambiguous_or_unknown_abbreviations_do_not_invent_matches():
    assert names("BS CE") == ["BS Civil Engineering"]
    assert names("CE") == ["BS Civil Engineering"]
    assert names("CPE") == ["BS Computer Engineering"]
    assert names("ZZZ") == []
    assert names("BEE") == []
    assert names("QQ") == []


def test_empty_course_code_still_recognizes_a_unique_abbreviation():
    index = ProgramIndex([
        {"college": "College of Computer Studies", "course": "BS Computer Science", "course_code": ""},
        {"college": "College of Nursing", "course": "BS Nursing", "course_code": ""},
    ])
    assert [item["course"] for item in index.programs_for_term("BS CS")] == ["BS Computer Science"]
    assert index.display_name("BS CS", "") == "BS Computer Science"


def test_stored_code_displays_the_catalog_name():
    index = ProgramIndex(PROGRAMS)
    assert index.display_name("BSCS", "BSCS", "College of Computer Studies") == "BS Computer Science"
    assert index.display_name("Bachelor of Science in Computer Science", "BSCS") == "BS Computer Science"
    assert index.display_name("BS Nursing", "BSN") == "BS Nursing"
    assert index.record_matches_term("BS CS", "Bachelor of Science in Computer Science", "BSCS")
    assert not index.record_matches_term("BS CS", "BS Nursing", "BSN")
    assert index.selection_matches("BS CS", "Bachelor of Science in Computer Science", "BSCS")
    assert not index.selection_matches("Not a real course", "BS Nursing", "BSN")


def _admin(client):
    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(admin["access_token"])


def _emails(response):
    return {row.get("email") or row.get("personal_email") for row in response.json()["items"]}


def test_registry_and_approvals_search_abbreviations(client):
    headers = _admin(client)
    computer = "carlos.mendoza@gmail.com"
    information = "maria.reyes@gmail.com"

    by_abbreviation = client.get(
        "/api/admin/university-records",
        headers=headers,
        params={"q": "  BS   CS ", "page_size": 25},
    )
    assert by_abbreviation.status_code == 200
    assert computer in _emails(by_abbreviation)
    assert information not in _emails(by_abbreviation)
    carlos = next(row for row in by_abbreviation.json()["items"] if row["personal_email"] == computer)
    assert "Computer Science" in carlos["degree"]
    assert carlos["degree"] != "BSCS"

    by_name = client.get(
        "/api/admin/university-records",
        headers=headers,
        params={"q": "computer science", "page_size": 25},
    )
    assert computer in _emails(by_name)
    assert information not in _emails(by_name)

    by_partial = client.get(
        "/api/admin/university-records",
        headers=headers,
        params={"q": "Comp Sci", "page_size": 25},
    )
    assert computer in _emails(by_partial)

    by_code = client.get(
        "/api/admin/university-records",
        headers=headers,
        params={"course": "BSCS", "page_size": 25},
    )
    assert computer in _emails(by_code)
    assert information not in _emails(by_code)
    assert by_code.json()["items"]
    assert all("Computer Science" in row["degree"] for row in by_code.json()["items"])

    unknown = client.get(
        "/api/admin/university-records",
        headers=headers,
        params={"q": "ZZZ-NOT-A-PROGRAM", "page_size": 25},
    )
    assert unknown.json()["total"] == 0

    approvals = client.get(
        "/api/admin/approvals",
        headers=headers,
        params={"q": "BS CS", "status": "All", "page_size": 25},
    )
    assert approvals.status_code == 200
    assert computer in _emails(approvals)
    assert information not in _emails(approvals)
    shown = next(row for row in approvals.json()["items"] if row["email"] == computer)
    assert "Computer Science" in shown["degree"]

    directory = client.get(
        "/api/admin/directory",
        headers=headers,
        params={"cohort": "all", "q": "BS IT", "page_size": 25},
    )
    assert directory.status_code == 200
    assert information in _emails(directory)
    assert computer not in _emails(directory)

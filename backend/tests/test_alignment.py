from app.models import SocCode
from app.services.alignment import analyze_career_alignment, invalidate_soc_cache


def test_aligned_software_engineer_bsit(client, db_session):
    status, detail, soc, _ = analyze_career_alignment(
        db_session,
        "Software Engineer",
        "Bachelor of Science in Information Technology",
    )
    assert status == "Aligned"
    assert soc is not None


def test_misaligned_restaurant_manager_bsit(client, db_session):
    status, detail, soc, _ = analyze_career_alignment(
        db_session,
        "Restaurant Manager",
        "Bachelor of Science in Information Technology",
    )
    assert status == "Misaligned"
    assert soc is not None


def test_unknown_without_job_title(client, db_session):
    status, detail, soc, _ = analyze_career_alignment(db_session, "", "BSIT")
    assert status == "Unknown"
    assert soc is None


def test_empty_degree_patterns_unknown(client, db_session):
    invalidate_soc_cache()
    db_session.add(
        SocCode(
            soc_code="9998",
            code="9998",
            description="Unique Audit Role",
            title_patterns="unique audit plumber",
            degree_patterns="",
            category="Test",
        )
    )
    db_session.commit()
    invalidate_soc_cache()
    status, detail, soc, _ = analyze_career_alignment(
        db_session,
        "Unique Audit Plumber",
        "Bachelor of Science in Information Technology",
    )
    assert status == "Unknown"
    assert "no degree pathways" in detail.lower()
    assert soc is not None
    assert soc.soc_code == "9998"

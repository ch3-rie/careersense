from datetime import date, timedelta

from app.models import Account, AlumniCard, TracerSubmission
from app.services.alumni_hub import build_aac_prefill, card_for_alumni, ensure_card
from tests.conftest import auth_header, login


def test_unemployed_graduate_can_apply_after_gts(client, db_session):
    user = db_session.query(Account).filter(Account.personal_email == "liza.torres@gmail.com").one()
    submission = (
        db_session.query(TracerSubmission)
        .filter(TracerSubmission.account_id == user.id)
        .one()
    )
    original = dict(submission.data_json or {})
    submission.data_json = {
        **original,
        "is_currently_employed": "No",
        "pres_emp": "",
        "pres_occ": "",
        "current_employer": "",
        "current_occupation": "",
    }
    db_session.commit()
    db_session.refresh(user)
    try:
        card = card_for_alumni(db_session, user, ensure_card(db_session, user))
        prefill = {field["key"]: field for field in build_aac_prefill(db_session, user)}
        assert card["gts_completed"] is True
        assert card["can_apply"] is True
        assert "company_affiliation" not in prefill
        assert prefill["college"]["origin"] == "registry"
        assert prefill["student_id"]["locked"] is True
    finally:
        submission.data_json = original
        db_session.commit()


def test_aac_stays_unavailable_without_a_submitted_gts(client, db_session):
    user = db_session.query(Account).filter(Account.personal_email == "liza.torres@gmail.com").one()
    holder = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
    rows = db_session.query(TracerSubmission).filter(TracerSubmission.account_id == user.id).all()
    owned = [row.id for row in rows]
    for row in rows:
        row.account_id = holder.id
    db_session.commit()
    try:
        card = card_for_alumni(db_session, user, ensure_card(db_session, user))
        assert card["gts_completed"] is False
        assert card["can_apply"] is False
    finally:
        for row in db_session.query(TracerSubmission).filter(TracerSubmission.id.in_(owned)).all():
            row.account_id = user.id
        db_session.commit()


def test_full_appointment_slot_is_hidden(client, db_session):
    from app.models import AacAppointmentSlot

    admin = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    headers = auth_header(admin["access_token"])
    slot_date = date.today() + timedelta(days=40)
    created = client.post(
        "/api/admin/cards/slots",
        headers=headers,
        json={"slot_date": slot_date.isoformat(), "slot_time": "16:00", "capacity": 1},
    )
    assert created.status_code == 200, created.text
    slot = db_session.query(AacAppointmentSlot).filter(AacAppointmentSlot.slot_time == "16:00").one()
    holder = db_session.query(Account).filter(Account.personal_email == "maria.reyes@gmail.com").one()
    card = holder.alumni_card or AlumniCard(account_id=holder.id, status="Claimed")
    previous = dict(card.application_json or {})
    card.application_json = {"appointment_date": slot_date.isoformat(), "appointment_time": "16:00"}
    db_session.add(card)
    db_session.commit()
    try:
        alumni = login(client, "liza.torres@gmail.com", "Alumni@2026")
        body = client.get("/api/alumni/card", headers=auth_header(alumni["access_token"])).json()
        times = [
            item["time"]
            for day in body["appointments"]
            if day["date"] == slot_date.isoformat()
            for item in day["times"]
        ]
        assert "16:00" not in times
    finally:
        card.application_json = previous
        db_session.commit()

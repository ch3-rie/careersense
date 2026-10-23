from datetime import date, datetime, timezone

from app.services.card_renewal import add_years, assess_card_renewal


def test_records_outside_batch_2027_stay_undefined():
    claimed = datetime(2022, 6, 20, 3, 0, tzinfo=timezone.utc)
    for year in ("2016", "2024", "2026", "", "27", None):
        result = assess_card_renewal(year, claimed, today=date(2026, 10, 22))
        assert result["id_status"] == "Undefined"
        assert result["eligibility"] == "not_determined"
        assert result["eligibility_label"] == "Not determined"
        assert result["next_renewal_on"] is None
        assert result["claiming_date"] == "2022-06-20"
        assert "existing records" in result["id_note"]


def test_batch_2027_without_claiming_date_is_not_due():
    result = assess_card_renewal("2027", None, today=date(2032, 1, 1))
    assert result["id_status"] == "Defined"
    assert result["eligibility"] == "not_yet"
    assert result["next_renewal_on"] is None
    assert "not marked due" in result["note"]


def test_four_year_cycle_uses_claiming_date_not_printing_or_graduation_year():
    claimed = datetime(2027, 3, 15, 1, 30, tzinfo=timezone.utc)
    before = assess_card_renewal("2027", claimed, today=date(2031, 3, 14))
    assert before["eligibility"] == "not_yet"
    assert before["claiming_date"] == "2027-03-15"
    assert before["next_renewal_on"] == "2031-03-15"

    on_day = assess_card_renewal("2027", claimed, today=date(2031, 3, 15))
    assert on_day["eligibility"] == "due"
    assert on_day["eligibility_label"] == "Due for renewal"
    assert "does not create a renewal request" in on_day["note"]


def test_stored_claiming_text_is_read_without_inventing_a_due_date():
    undefined = assess_card_renewal("2022", "2022-06-20T11:00:00", today=date(2026, 10, 22))
    assert undefined["claiming_date"] == "2022-06-20"
    assert undefined["next_renewal_on"] is None
    assert undefined["eligibility"] == "not_determined"

    due = assess_card_renewal("2027", "2027-03-15T11:00:00", today=date(2031, 3, 15))
    assert due["eligibility"] == "due"
    assert due["next_renewal_on"] == "2031-03-15"


def test_leap_day_claim_moves_to_february_28_when_needed():
    assert add_years(date(2028, 2, 29), 4) == date(2032, 2, 29)
    assert add_years(date(2028, 2, 29), 1) == date(2029, 2, 28)


def test_linked_pre_2027_batch_keeps_undefined_id_and_uses_claiming_date():
    claimed = datetime(2022, 2, 8, 4, 0, tzinfo=timezone.utc)
    linked = assess_card_renewal("2016", claimed, linked=True, today=date(2026, 10, 22))
    assert linked["id_status"] == "Undefined"
    assert linked["eligibility"] == "due"
    assert linked["eligibility_label"] == "Due for renewal"
    assert linked["claiming_date"] == "2022-02-08"
    assert linked["next_renewal_on"] == "2026-02-08"
    assert "undefined" in linked["note"].lower()
    assert "does not create a renewal request" in linked["note"]

    waiting = assess_card_renewal("2016", claimed, linked=True, today=date(2026, 2, 7))
    assert waiting["id_status"] == "Undefined"
    assert waiting["eligibility"] == "not_yet"
    assert waiting["next_renewal_on"] == "2026-02-08"


def test_linked_pre_2027_without_claiming_date_stays_unresolved():
    result = assess_card_renewal("2016", None, linked=True, today=date(2030, 1, 1))
    assert result["id_status"] == "Undefined"
    assert result["eligibility"] == "not_determined"
    assert result["next_renewal_on"] is None
    assert result["claiming_date"] is None
    assert "not marked due" in result["note"]
    assert "existing records" in result["note"]


def test_linked_account_without_a_batch_year_does_not_invent_a_cycle():
    result = assess_card_renewal("", "2022-06-20T11:00:00", linked=True, today=date(2026, 10, 22))
    assert result["id_status"] == "Undefined"
    assert result["eligibility"] == "not_determined"
    assert result["next_renewal_on"] is None

"""Renewal eligibility derived from the graduation year and the claiming date.

ID status and the four-year countdown stay separate. Batches before 2027 keep
an Undefined ID status. That status is not treated as expired, and it is not
replaced when a claiming date is available. A pre-2027 graduate who has not
linked a CareerSense account is not given a renewal eligibility result. Once
the account is linked to the graduate registry, the confirmed batch year
decides which rule applies. The countdown itself starts only on a recorded
claiming date. Account creation, printing, and the graduation year do not
start it. A missing claiming date is not replaced with another date, and
nothing here creates a renewal request or changes a card status.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

RENEWAL_BATCH_YEAR = 2027  # Batches before this year keep an Undefined ID status.
RENEWAL_YEARS = 4
MANILA = ZoneInfo("Asia/Manila")
UNDEFINED_NOTE = "ID status is undefined. The office must check its existing records."


def renewal_batch_year(year) -> int | None:
    text = str(year or "").strip()
    if len(text) == 4 and text.isdigit():
        return int(text)
    return None


def claiming_date(value) -> date | None:
    """Calendar date of a stored claiming timestamp.

    A value that already names a timezone is converted to Philippine time.
    A value stored without a timezone keeps its own calendar date, because
    that is the date shown to the office.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.date()
        return value.astimezone(MANILA).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return claiming_date(datetime.fromisoformat(text))
        except ValueError:
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                return None
    return None


def add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def _dated(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _unresolved(recorded: str | None, note: str) -> dict:
    return {
        "id_status": "Undefined",
        "id_note": UNDEFINED_NOTE,
        "eligibility": "not_determined",
        "eligibility_label": "Not determined",
        "claiming_date": recorded,
        "next_renewal_on": None,
        "note": note,
    }


def assess_card_renewal(year, issued_at, *, linked: bool = False, today: date | None = None) -> dict:
    """Return ID status and renewal eligibility without writing any card data."""
    current = today or datetime.now(MANILA).date()
    batch = renewal_batch_year(year)
    claimed = claiming_date(issued_at)
    recorded = claimed.isoformat() if claimed else None
    defined_batch = batch is not None and batch >= RENEWAL_BATCH_YEAR
    if not defined_batch and not linked:
        return _unresolved(recorded, UNDEFINED_NOTE)
    if not defined_batch and batch is None:
        return _unresolved(
            recorded,
            "The linked account does not have a confirmed four-digit batch year. "
            "A next renewal date is not calculated. The office must check its existing records.",
        )
    if not defined_batch and claimed is None:
        return _unresolved(
            None,
            f"Batch {batch} is confirmed from the linked graduate record. "
            "No claiming date is recorded, so a next renewal date is not calculated "
            "and the card is not marked due for renewal. The office must check its existing records.",
        )
    if defined_batch and claimed is None:
        return {
            "id_status": "Defined",
            "id_note": "",
            "eligibility": "not_yet",
            "eligibility_label": "Not yet eligible",
            "claiming_date": None,
            "next_renewal_on": None,
            "note": (
                f"Batch {batch} is within the renewal batches that start in {RENEWAL_BATCH_YEAR}. "
                "The four-year cycle starts on the claiming date. No claiming date is recorded, "
                "so a next renewal date is not calculated and the card is not marked due for renewal."
            ),
        }
    due_on = add_years(claimed, RENEWAL_YEARS)
    due = current >= due_on
    outcome = (
        "The card is due for renewal. This does not create a renewal request or change the card status."
        if due
        else "The card is not yet eligible for renewal."
    )
    if defined_batch:
        year_sentence = "The graduation year and the printing date do not start this cycle."
        id_note = ""
    else:
        year_sentence = (
            f"Batch {batch} is before {RENEWAL_BATCH_YEAR}, so the ID status stays Undefined. "
            "Renewal eligibility is calculated separately from the claiming date. "
            "The printing date and the account creation date do not start this cycle."
        )
        id_note = UNDEFINED_NOTE
    return {
        "id_status": "Defined" if defined_batch else "Undefined",
        "id_note": id_note,
        "eligibility": "due" if due else "not_yet",
        "eligibility_label": "Due for renewal" if due else "Not yet eligible",
        "claiming_date": claimed.isoformat(),
        "next_renewal_on": due_on.isoformat(),
        "note": (
            f"The next renewal date is {_dated(due_on)}, four years after the card was claimed on {_dated(claimed)}. "
            f"{year_sentence} {outcome}"
        ),
    }

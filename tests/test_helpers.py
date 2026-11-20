"""Canonical concert date validation shared by the API and entities."""

import pytest

from custom_components.setlistfm.helpers import normalize_concert


@pytest.mark.parametrize("date", [
    "1-1-2026", "1-01-2026", "01-1-2026", " 1-01-2026",
    "01-01-2026 ", "01- 1-2026", "2026-01-01", "01/01/2026",
    "29-02-2025", "31-04-2026", "01-01-0000",
])
def test_noncanonical_or_impossible_dates_are_rejected(date):
    with pytest.raises(ValueError):
        normalize_concert({"id": "concert", "eventDate": date})


@pytest.mark.parametrize("date", [
    "01-01-2026", "31-12-2026", "29-02-2024", "29-02-2000",
    "01-01-0001", "01-01-0099", "31-12-0999", "31-12-9999",
])
def test_canonical_dates_are_preserved(date):
    record = {"id": "concert", "eventDate": date}
    normalized, repaired = normalize_concert(record)
    assert normalized["eventDate"] == record["eventDate"] == date
    assert not repaired

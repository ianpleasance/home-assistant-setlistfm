"""Venue-day grouping uses full records, without mutating or guessing identity."""
from copy import deepcopy
from datetime import date

import pytest

from custom_components.setlistfm.coordinator import SetlistFmCoordinator
from custom_components.setlistfm.helpers import normalize_concert
from custom_components.setlistfm.sensor import SetlistFmUniqueConcertVisitsSensor
from custom_components.setlistfm.visits import ConcertVisits


def concert(key, venue="venue", day="01-01-2026", artist="Bloodywood"):
    return normalize_concert({
        "id": key, "eventDate": day,
        "artist": {"name": artist},
        "venue": {"id": venue, "name": "Same venue name", "city": {"name": "City"}},
        "url": f"https://www.setlist.fm/setlist/{key}.html",
        "set": [{"song": [{"name": "Song"}]}],
    })[0]


def snapshot(records, *, complete=True):
    return {
        "concerts": records, "total": len(records), "fetched_count": len(records),
        "skipped_count": 0, "complete": complete,
        "completeness_reason": None if complete else "invalid_records", "pages_fetched": 1,
    }


def test_venue_day_identity_and_deterministic_lineups():
    records = [
        concert("support", artist="Support"),
        concert("headliner"),
        concert("next-day", day="02-01-2026"),
        concert("other-venue", venue="other"),
        concert("different-city", venue="another"),
    ]
    records[-1]["venue"]["city"]["name"] = "Other city"
    original = deepcopy(records)
    visits = ConcertVisits(snapshot(records))
    assert visits.count == 4
    grouped = visits.display(date(2026, 2, 1), "all", 50)
    shared = next(visit for visit in grouped if visit["performance_count"] == 2)
    assert [record["id"] for record in shared["performances"]] == ["headliner", "support"]
    assert shared["grouping_complete"] is True
    assert shared["omitted_performance_count"] == 0
    assert records == original
    assert ConcertVisits(snapshot(list(reversed(records)))).display(date(2026, 2, 1), "all", 50) == grouped


@pytest.mark.parametrize("identity", [None, "", " ", " venue", "venue ", 42, {}, [], True])
def test_missing_and_malformed_identity_never_merge(identity):
    records = [concert("first", venue=identity), concert("second", venue=identity), concert("identified")]
    visits = ConcertVisits(snapshot(records))
    assert visits.count is None
    assert visits.metadata == {
        "grouping_rule": "venue_day", "grouping_complete": False,
        "identified_visit_count": 1, "unidentified_performance_count": 2,
        "invalid_date_count": 0,
    }
    grouped = visits.display(date(2026, 1, 1), "all", 50)
    assert len(grouped) == 3
    assert sum(not visit["grouping_complete"] for visit in grouped) == 2
    assert {record["id"] for visit in grouped for record in visit["performances"]} == {"first", "second", "identified"}


@pytest.mark.parametrize("show,expected", [
    ("all", ["today", "tomorrow", "later"]),
    ("upcoming", ["today", "tomorrow", "later"]),
    ("past", ["yesterday", "older"]),
])
def test_group_before_filter_and_limit(show, expected):
    records = [
        concert("older", day="01-01-2026"), concert("yesterday", day="04-01-2026"),
        concert("today", day="05-01-2026"), concert("today-support", day="05-01-2026", artist="Support"),
        concert("tomorrow", day="06-01-2026"), concert("later", day="07-01-2026"),
    ]
    visits = ConcertVisits(snapshot(records))
    grouped = visits.display(date(2026, 1, 5), show, 3)
    assert [visit["performances"][0]["id"] for visit in grouped] == expected
    assert visits.count == 5
    if show != "past":
        assert len(grouped[0]["performances"]) == 2


@pytest.mark.parametrize("day", ["01-01-0001", "31-12-9999"])
def test_canonical_date_extremes(day):
    visits = ConcertVisits(snapshot([concert("first", day=day), concert("support", day=day)]))
    assert visits.count == 1
    assert visits.display(date(2026, 1, 1), "all", 10)[0]["date"] == day


def test_defensive_bad_date_cannot_make_known_count(caplog):
    records = [concert("valid"), {**concert("invalid"), "eventDate": "1-1-2026"}]
    visits = ConcertVisits(snapshot(records))
    assert visits.count is None
    assert visits.metadata["invalid_date_count"] == 1
    assert "invalid event date" in caplog.text


@pytest.mark.parametrize("complete,expected", [(True, 0), (False, None)])
def test_explicit_empty_vs_incomplete(complete, expected):
    visits = ConcertVisits(snapshot([], complete=complete))
    assert visits.count == expected
    assert visits.display(date(2026, 1, 1), "all", 10) == []


def test_partial_known_identities_are_not_an_exact_total():
    visits = ConcertVisits(snapshot([concert("headliner"), concert("support")], complete=False))
    assert visits.count is None
    assert visits.metadata["identified_visit_count"] == 1
    assert visits.metadata["unidentified_performance_count"] == 0
    assert visits.metadata["grouping_complete"] is False


def test_festival_resource_limits_are_explicit_and_never_erase_a_visit():
    records = [
        concert(f"{venue}-{index:03d}", venue=f"{venue:02d}")
        for venue in range(51) for index in range(130)
    ]
    visits = ConcertVisits(snapshot(records))
    grouped = visits.display(date(2026, 1, 1), "all", 50)
    assert visits.count == 51
    assert visits.metadata["grouping_complete"] is True
    assert len(grouped) == 50
    assert sum(len(visit["performances"]) for visit in grouped) == 500
    assert grouped[0]["performance_count"] == 130
    assert grouped[0]["omitted_performance_count"] == 30
    for visit in grouped:
        assert 1 <= len(visit["performances"]) <= 100
        assert visit["performance_count"] == 130
        assert len(visit["performances"]) + visit["omitted_performance_count"] == 130


async def test_cache_is_shared_and_replaced_with_new_snapshot(hass, entry):
    coordinator = SetlistFmCoordinator(hass, entry)
    sensor = SetlistFmUniqueConcertVisitsSensor(coordinator, entry)
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}
    coordinator.async_set_updated_data(snapshot([concert("one")]))
    before = coordinator.concert_visits
    assert sensor.native_value == 1
    assert coordinator.concert_visits is before
    coordinator.async_set_updated_data(snapshot([concert("one"), concert("two", venue="other")]))
    assert sensor.native_value == 2
    assert coordinator.concert_visits is not before

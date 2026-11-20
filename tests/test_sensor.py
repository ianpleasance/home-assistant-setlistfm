"""Compatible simplified attributes for documented and recorded response shapes."""
from datetime import timedelta
import json
from pathlib import Path

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.setlistfm import SetlistFmCoordinator
from custom_components.setlistfm.const import (
    CONF_API_KEY, CONF_NUMBER_OF_CONCERTS, CONF_SHOW_CONCERTS, CONF_USERID, DOMAIN,
)
from custom_components.setlistfm.sensor import SetlistFmConcertsSensor


def make_sensor(hass, data, *, limit=50, show="all"):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERID: "Blabla", CONF_API_KEY: "secret"},
        options={CONF_NUMBER_OF_CONCERTS: limit, CONF_SHOW_CONCERTS: show},
    )
    coordinator = SetlistFmCoordinator(hass, entry)
    coordinator.async_set_updated_data(data)
    return SetlistFmConcertsSensor(coordinator, entry)


async def test_schema_fixtures(hass, aioclient_mock, caplog):
    records = json.loads(
        (Path(__file__).parent / "fixtures" / "concerts.json").read_text()
    )
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERID: "blabla", CONF_API_KEY: "secret"}
    )
    coordinator = SetlistFmCoordinator(hass, entry)
    aioclient_mock.get(
        "https://api.setlist.fm/rest/1.0/user/blabla/attended?p=1",
        json={"setlist": records, "total": len(records), "page": 1, "itemsPerPage": 20},
    )
    data = await coordinator._async_update_data()
    sensor = make_sensor(hass, data)
    attrs = sensor.extra_state_attributes
    by_id = {item["id"]: item for item in attrs["concerts"]}
    assert sensor.native_value == 6
    assert by_id["documented"]["song_count"] == by_id["deployed"]["song_count"] == 3
    assert by_id["both"]["song_count"] == 1
    assert by_id["empty"]["song_count"] == by_id["optional"]["song_count"] == 0
    assert by_id["malformed-optional"]["song_count"] == 1
    assert by_id["documented"] == {
        "id": "documented", "date": "01-01-2026",
        "artist": {"name": "Example Artist", "mbid": "example-mbid"},
        "venue": {
            "name": "Example Venue", "city": "Example City",
            "state": "Example State", "country": "Example Country",
        },
        "song_count": 3,
        "url": "https://www.setlist.fm/setlist/example/documented.html",
    }
    assert by_id["optional"]["artist"] == {"name": "Unknown", "mbid": None}
    assert by_id["optional"]["venue"] == {
        "name": "Unknown", "city": "", "state": "", "country": ""
    }
    assert attrs["total_attended"] == 8
    assert attrs["fetched_count"] == 6
    assert attrs["skipped_count"] == 2
    assert attrs["complete"] is False
    assert attrs["completeness_reason"] == "invalid_records"
    assert len(attrs["concert_list"].splitlines()) == 6
    assert "Data provided by setlist.fm" in attrs["attribution"]
    assert "skipped 2 records" in caplog.text


@pytest.mark.parametrize("limit", [1, 10, 50])
async def test_display_limit_after_all_pages(hass, aioclient_mock, limit):
    """Sort all pages locally; do not assume the server's date ordering."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERID: "blabla", CONF_API_KEY: "secret"}
    )
    coordinator = SetlistFmCoordinator(hass, entry)
    today = dt_util.now().date()
    records = [
        {"id": str(index), "eventDate": (today + timedelta(days=index)).strftime("%d-%m-%Y")}
        for index in range(42)
    ]
    for number in (1, 2, 3):
        aioclient_mock.get(
            f"https://api.setlist.fm/rest/1.0/user/blabla/attended?p={number}",
            json={
                "setlist": records[(number - 1) * 20:number * 20],
                "total": 42, "page": number, "itemsPerPage": 20,
            },
        )
    data = await coordinator._async_update_data()
    sensor = make_sensor(hass, data, limit=limit)
    assert sensor.native_value == min(limit, 42)
    attrs = sensor.extra_state_attributes
    assert attrs["total_attended"] == attrs["fetched_count"] == 42
    assert attrs["concerts"][0]["id"] == "41"
    assert attrs["complete"]
    assert aioclient_mock.call_count == 3


@pytest.mark.parametrize("show,expected", [("past", ["past"]), ("upcoming", ["future", "today"])])
async def test_filters_and_bad_date_isolation(hass, show, expected):
    today = dt_util.now().date()
    records = [
        {"id": name, "eventDate": (today + timedelta(days=offset)).strftime("%d-%m-%Y")}
        for name, offset in (("past", -1), ("today", 0), ("future", 1))
    ]
    records.append({"id": "bad", "eventDate": "invalid"})
    sensor = make_sensor(hass, {
        "concerts": records, "total": 4, "fetched_count": 3, "skipped_count": 1,
        "complete": False, "completeness_reason": "invalid_records", "pages_fetched": 1,
    }, show=show)
    assert [item["id"] for item in sensor.extra_state_attributes["concerts"]] == expected

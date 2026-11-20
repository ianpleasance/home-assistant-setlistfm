"""Native entity registration, action targeting and lifecycle regression tests."""
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.setlistfm.api import SetlistFmConnectionError
from custom_components.setlistfm.const import (
    CONF_API_KEY,
    CONF_NUMBER_OF_CONCERTS,
    CONF_REFRESH_PERIOD,
    CONF_SHOW_CONCERTS,
    CONF_USERID,
    DOMAIN,
)


def entity_id(hass, entry, suffix, platform="sensor"):
    return er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{entry.entry_id}_{suffix}"
    )


async def load(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def refresh(hass, data=None):
    await hass.services.async_call(DOMAIN, "refresh", data or {}, blocking=True)


async def test_native_overview(hass, entry, mock_attendance, freezer):
    freezer.move_to("2026-02-01T12:00:00+00:00")
    hass.config_entries.async_update_entry(
        entry, options={CONF_SHOW_CONCERTS: "past", CONF_NUMBER_OF_CONCERTS: 1}
    )
    await load(hass, entry)
    assert DOMAIN not in hass.data
    assert entry.runtime_data.config_entry is entry
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 6
    assert sum(item.entity_id.startswith("sensor.") for item in entities) == 5
    assert all(item.has_entity_name for item in entities)
    assert len({item.device_id for item in entities}) == 1
    device = dr.async_get(hass).async_get(entities[0].device_id)
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.configuration_url == "https://www.setlist.fm/user/blabla"
    assert device.entry_type is dr.DeviceEntryType.SERVICE

    concerts = hass.states.get(entity_id(hass, entry, "concerts"))
    assert concerts.state == "1"
    assert concerts.attributes["friendly_name"] == "My shows Concerts shown"
    assert concerts.attributes["concerts"][0]["id"] == "past"
    assert "state_class" not in concerts.attributes
    assert concerts.attributes["total_attended"] == 4
    assert hass.states.get(entity_id(hass, entry, "total_concerts")).state == "4"
    visits = hass.states.get(entity_id(hass, entry, "unique_concert_visits"))
    assert visits.state == "4"
    assert visits.attributes["friendly_name"] == "My shows Unique concert visits"
    assert visits.attributes["icon"] == "mdi:calendar-check-outline"
    assert "state_class" not in visits.attributes
    assert "unit_of_measurement" not in visits.attributes
    assert "concert_visits" not in visits.attributes
    assert visits.attributes["grouping_complete"] is True
    assert registry.async_get(visits.entity_id).unique_id == f"{entry.entry_id}_unique_concert_visits"
    assert len(concerts.attributes["concert_visits"]) == 1
    next_concert = hass.states.get(entity_id(hass, entry, "next_concert"))
    assert next_concert.state == "2026-02-01"
    assert next_concert.attributes["device_class"] == "date"
    assert next_concert.attributes["artist"] == "Artist today"
    assert next_concert.attributes["venue"] == "Venue today"
    assert next_concert.attributes["url"].endswith("/today.html")
    assert "concerts" not in next_concert.attributes
    updated = hass.states.get(entity_id(hass, entry, "last_update"))
    assert updated.attributes["friendly_name"] == "My shows Last successful update"
    assert dt_util.parse_datetime(updated.state) == concerts.attributes["last_updated"]
    assert updated.attributes["device_class"] == "timestamp"
    assert registry.async_get(updated.entity_id).entity_category is EntityCategory.DIAGNOSTIC
    button_id = entity_id(hass, entry, "refresh", "button")
    assert registry.async_get(button_id).entity_category is EntityCategory.CONFIG
    assert "device_class" not in hass.states.get(button_id).attributes
    assert mock_attendance.await_count == 1


async def test_incomplete_coverage_is_not_a_failed_fetch(
    hass, entry, mock_attendance, attendance, freezer
):
    freezer.move_to("2026-02-01T12:00:00+00:00")
    attendance.update(
        total=6, skipped_count=2, complete=False, completeness_reason="invalid_records"
    )
    await load(hass, entry)
    assert hass.states.get(entity_id(hass, entry, "total_concerts")).state == "6"
    visits = hass.states.get(entity_id(hass, entry, "unique_concert_visits"))
    assert visits.state == "unknown"
    assert visits.attributes["identified_visit_count"] == 4
    assert visits.attributes["grouping_complete"] is False
    upcoming = hass.states.get(entity_id(hass, entry, "next_concert"))
    assert upcoming.state == "2026-02-01"
    assert upcoming.attributes["complete"] is False
    assert upcoming.attributes["completeness_reason"] == "invalid_records"
    assert entry.runtime_data.last_successful_update == dt_util.utcnow()
    assert entry.runtime_data.last_update_success


async def test_no_upcoming_setlist_clears_context(hass, entry, mock_attendance, freezer):
    freezer.move_to("2026-02-01T12:00:00+00:00")
    await load(hass, entry)
    next_id = entity_id(hass, entry, "next_concert")
    assert "artist" in hass.states.get(next_id).attributes
    freezer.move_to("2026-02-11T12:00:00+00:00")
    entry.runtime_data.async_update_local_date(dt_util.now())
    state = hass.states.get(next_id)
    assert state.state == "unknown"
    assert "artist" not in state.attributes
    assert "venue" not in state.attributes
    assert "url" not in state.attributes
    assert mock_attendance.await_count == 1


@pytest.mark.parametrize(
    "total,complete,reason",
    [(0, True, None), (None, False, "attendance_not_found")],
)
async def test_empty_and_ambiguous_accounts(
    hass, entry, mock_attendance, attendance, total, complete, reason
):
    attendance.update(
        concerts=[], total=total, fetched_count=0,
        complete=complete, completeness_reason=reason,
    )
    await load(hass, entry)
    assert hass.states.get(entity_id(hass, entry, "concerts")).state == "0"
    assert hass.states.get(entity_id(hass, entry, "total_concerts")).state == (
        "0" if total == 0 else "unknown"
    )
    assert hass.states.get(entity_id(hass, entry, "unique_concert_visits")).state == (
        "0" if total == 0 else "unknown"
    )
    next_concert = hass.states.get(entity_id(hass, entry, "next_concert"))
    assert next_concert.state == "unknown"
    assert next_concert.attributes["complete"] is complete
    assert next_concert.attributes["completeness_reason"] == reason
    assert "artist" not in next_concert.attributes
    assert hass.states.get(entity_id(hass, entry, "last_update")).state != "unknown"


async def test_availability_and_button_retry(hass, entry, mock_attendance):
    await load(hass, entry)
    timestamp = entry.runtime_data.last_successful_update
    snapshot = entry.runtime_data.concert_visits
    mock_attendance.side_effect = SetlistFmConnectionError("offline")
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    for suffix in ("concerts", "total_concerts", "unique_concert_visits", "next_concert", "last_update"):
        assert hass.states.get(entity_id(hass, entry, suffix)).state == "unavailable"
    assert entry.runtime_data.last_successful_update == timestamp
    assert entry.runtime_data.concert_visits is snapshot
    assert snapshot.count == 4
    button_id = entity_id(hass, entry, "refresh", "button")
    assert hass.states.get(button_id).state != "unavailable"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {"entity_id": button_id}, blocking=True
        )
    mock_attendance.side_effect = None
    await hass.services.async_call(
        "button", "press", {"entity_id": button_id}, blocking=True
    )
    assert hass.states.get(entity_id(hass, entry, "total_concerts")).state == "4"
    assert hass.states.get(entity_id(hass, entry, "unique_concert_visits")).state == "4"
    assert entry.runtime_data.last_exception is None


@pytest.mark.parametrize("custom_name", [None, "My custom concert name"])
async def test_custom_registry_identity_options_reload_and_unload(
    hass, entry, mock_attendance, custom_name,
):
    registry = er.async_get(hass)
    existing = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_concerts",
        config_entry=entry, suggested_object_id="my_existing_concerts",
        original_name="Concerts",
    )
    registry.async_update_entity(existing.entity_id, name=custom_name)
    await load(hass, entry)
    before = registry.async_get(existing.entity_id)
    assert before.unique_id == existing.unique_id
    assert before.original_name == "Concerts shown"
    assert before.translation_key == "concerts"
    expected_name = custom_name or "My shows Concerts shown"
    assert hass.states.get(existing.entity_id).attributes["friendly_name"] == expected_name
    ids = {item.entity_id for item in er.async_entries_for_config_entry(registry, entry.entry_id)}
    visits_id = entity_id(hass, entry, "unique_concert_visits")
    registry.async_update_entity(visits_id, name="My venue days")
    old_coordinator = entry.runtime_data
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={
            CONF_REFRESH_PERIOD: 12, CONF_NUMBER_OF_CONCERTS: 1,
            "date_format": "%d-%m-%Y", CONF_SHOW_CONCERTS: "all",
        },
    )
    await hass.async_block_till_done()
    assert entry.runtime_data is not old_coordinator
    assert old_coordinator._shutdown_requested
    assert not old_coordinator._listeners
    assert old_coordinator._unsub_refresh is None
    assert entry.runtime_data.update_interval == timedelta(hours=12)
    assert hass.states.get(existing.entity_id).state == "1"
    after = registry.async_get(existing.entity_id)
    assert after.id == before.id
    assert after.device_id == before.device_id
    assert after.name == custom_name
    assert after.original_name == "Concerts shown"
    assert after.unique_id == existing.unique_id
    assert hass.states.get(existing.entity_id).attributes["friendly_name"] == expected_name
    assert {item.entity_id for item in er.async_entries_for_config_entry(registry, entry.entry_id)} == ids
    assert hass.states.get(visits_id).attributes["friendly_name"] == "My venue days"
    assert hass.states.get(visits_id).state == "4"
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.services.has_service(DOMAIN, "refresh")
    with pytest.raises(ServiceValidationError):
        await refresh(hass, {"entry_id": entry.entry_id})
    with pytest.raises(ServiceValidationError):
        await refresh(hass)
    await load(hass, entry)
    assert entity_id(hass, entry, "concerts") == existing.entity_id
    assert hass.states.get(existing.entity_id).attributes["friendly_name"] == expected_name


@pytest.mark.parametrize("target", ["", "missing", "foreign", "unloaded"])
async def test_explicit_invalid_target_never_refreshes_all(
    hass, entry, mock_attendance, target
):
    await load(hass, entry)
    if target in ("foreign", "unloaded"):
        other = MockConfigEntry(
            domain="sensor" if target == "foreign" else DOMAIN, data={}
        )
        other.add_to_hass(hass)
        target = other.entry_id
    with pytest.raises(ServiceValidationError):
        await refresh(hass, {"entry_id": target})
    assert mock_attendance.await_count == 1


@pytest.mark.parametrize("data", [{"entry_id": None}, {"entry_id": []}, {"typo": "missing"}])
async def test_invalid_schema(hass, entry, mock_attendance, data):
    await load(hass, entry)
    with pytest.raises(vol.Invalid):
        await refresh(hass, data)
    assert mock_attendance.await_count == 1


async def test_service_without_entries_and_failed_setup(hass, mock_attendance):
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "refresh")
    with pytest.raises(ServiceValidationError):
        await refresh(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERID: "blabla", CONF_API_KEY: "secret"}
    )
    entry.add_to_hass(hass)
    mock_attendance.side_effect = SetlistFmConnectionError("offline")
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.services.has_service(DOMAIN, "refresh")
    with pytest.raises(ServiceValidationError):
        await refresh(hass, {"entry_id": entry.entry_id})


async def test_multi_entry_refresh_and_failure_aggregation(hass, entry, mock_attendance):
    await load(hass, entry)
    other = MockConfigEntry(
        domain=DOMAIN, title="Other shows",
        data={CONF_USERID: "other", CONF_API_KEY: "secret"},
    )
    other.add_to_hass(hass)
    await load(hass, other)
    assert len(dr.async_get(hass).devices) == 2
    with (
        patch.object(entry.runtime_data, "async_manual_refresh", new_callable=AsyncMock) as first,
        patch.object(other.runtime_data, "async_manual_refresh", new_callable=AsyncMock) as second,
    ):
        await refresh(hass, {"entry_id": entry.entry_id})
        assert first.await_count == 1 and second.await_count == 0
        await refresh(hass)
        assert first.await_count == 2 and second.await_count == 1
        first.side_effect = HomeAssistantError("offline")
        with pytest.raises(HomeAssistantError, match="offline"):
            await refresh(hass)
        assert first.await_count == 3 and second.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    await refresh(hass)
    assert other.state is ConfigEntryState.LOADED


async def test_local_midnight_without_fetch_and_listener_cleanup(
    hass, entry, mock_attendance, freezer
):
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Amsterdam"))
    freezer.move_to("2026-02-01T22:59:59+00:00")
    hass.config_entries.async_update_entry(entry, options={CONF_SHOW_CONCERTS: "upcoming"})
    await load(hass, entry)
    timestamp = entry.runtime_data.last_successful_update
    next_id = entity_id(hass, entry, "next_concert")
    assert hass.states.get(next_id).state == "2026-02-01"
    concerts_id = entity_id(hass, entry, "concerts")
    assert hass.states.get(concerts_id).state == "3"
    groups = entry.runtime_data.concert_visits
    assert [visit["date"] for visit in hass.states.get(concerts_id).attributes["concert_visits"]] == [
        "01-02-2026", "02-02-2026", "10-02-2026",
    ]
    freezer.move_to("2026-02-01T23:00:01+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get(next_id).state == "2026-02-02"
    assert hass.states.get(concerts_id).state == "2"
    assert [visit["date"] for visit in hass.states.get(concerts_id).attributes["concert_visits"]] == [
        "02-02-2026", "10-02-2026",
    ]
    assert entry.runtime_data.concert_visits is groups
    assert hass.states.get(entity_id(hass, entry, "unique_concert_visits")).state == "4"
    assert mock_attendance.await_count == 1
    assert entry.runtime_data.last_successful_update == timestamp
    coordinator = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    with patch.object(coordinator, "async_update_listeners") as notify:
        freezer.move_to("2026-02-02T23:00:01+00:00")
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        notify.assert_not_called()


async def test_repeated_service_and_button_wait_for_own_result(
    hass, entry, mock_attendance
):
    await load(hass, entry)
    await refresh(hass)
    mock_attendance.side_effect = SetlistFmConnectionError("second call failed")
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    assert mock_attendance.await_count == 3
    mock_attendance.side_effect = None
    button_id = entity_id(hass, entry, "refresh", "button")
    await hass.services.async_call("button", "press", {"entity_id": button_id}, blocking=True)
    mock_attendance.side_effect = SetlistFmConnectionError("button call failed")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("button", "press", {"entity_id": button_id}, blocking=True)
    assert mock_attendance.await_count == 5


async def test_concurrent_service_button_and_scheduled_refresh(
    hass, entry, mock_attendance, attendance
):
    await load(hass, entry)
    started = asyncio.Event()
    release = asyncio.Event()
    active = 0
    maximum = 0
    calls = 0

    async def fetch():
        nonlocal active, maximum, calls
        active += 1
        maximum = max(maximum, active)
        calls += 1
        current = calls
        if current == 1:
            started.set()
            await release.wait()
        active -= 1
        if current == 2:
            raise SetlistFmConnectionError("second operation failed")
        return attendance

    mock_attendance.side_effect = fetch
    first = asyncio.create_task(refresh(hass))
    await started.wait()
    button_id = entity_id(hass, entry, "refresh", "button")
    second = asyncio.create_task(hass.services.async_call(
        "button", "press", {"entity_id": button_id}, blocking=True
    ))
    third = asyncio.create_task(entry.runtime_data._handle_refresh_interval())
    await asyncio.sleep(0)
    assert not first.done() and not second.done()
    release.set()
    results = await asyncio.gather(first, second, third, return_exceptions=True)
    assert results[0] is None
    assert isinstance(results[1], HomeAssistantError)
    assert results[2] is None
    assert calls == 3 and maximum == 1
    assert entry.runtime_data.last_update_success

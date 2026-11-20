"""Regression tests for usernames in existing config entries."""

import asyncio
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState, current_entry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.setlistfm import SetlistFmCoordinator
from custom_components.setlistfm import api
from custom_components.setlistfm.config_flow import validate_input
from custom_components.setlistfm.const import CONF_API_KEY, CONF_USERID, DOMAIN
from custom_components.setlistfm.sensor import SetlistFmConcertsSensor
from custom_components.setlistfm.sensor import SetlistFmLastUpdateSensor
from custom_components.setlistfm.api import SetlistFmConnectionError
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util


@pytest.mark.parametrize("username", ["Blabla", "BLABLA", "blabla", " Blabla "])
async def test_existing_entry_requests_use_lowercase(
    hass: HomeAssistant, aioclient_mock, username: str
) -> None:
    """Normalize the supported endpoint without migrating registry identities."""
    api_key = "CaseSensitive-API-Key"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=username,
        data={CONF_USERID: username, CONF_API_KEY: api_key},
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(
        "https://api.setlist.fm/rest/1.0/user/blabla/attended?p=1",
        json={
            "setlist": [{"id": "concert-id", "eventDate": "01-01-2026"}],
            "total": 1, "page": 1, "itemsPerPage": 20,
        },
    )

    coordinator = SetlistFmCoordinator(hass, entry)
    data = await coordinator._async_update_data()

    assert data["concerts"][0]["id"] == "concert-id"
    assert data["total"] == data["fetched_count"] == 1
    assert data["complete"]
    assert "user" not in data
    assert coordinator.userid == "blabla"
    assert coordinator.api_key == api_key
    assert aioclient_mock.call_count == 1
    for _, _, _, headers in aioclient_mock.mock_calls:
        assert headers == {"x-api-key": api_key, "Accept": "application/json"}
    assert entry.data[CONF_USERID] == username
    assert entry.unique_id == username
    sensor = SetlistFmConcertsSensor(coordinator, entry)
    assert sensor.unique_id == f"{entry.entry_id}_concerts"
    assert sensor.device_info["identifiers"] == {(DOMAIN, entry.entry_id)}


@pytest.mark.parametrize("status", [404, 429, 500])
async def test_later_page_failure_preserves_snapshot(hass, aioclient_mock, status):
    """A refresh failure retains all data from the previous successful refresh."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERID: "blabla", CONF_API_KEY: "secret"}
    )
    entry.add_to_hass(hass)
    coordinator = SetlistFmCoordinator(hass, entry)
    previous = {
        "concerts": [{"id": "old", "eventDate": "01-01-2025"}],
        "total": 1, "fetched_count": 1, "skipped_count": 0,
        "complete": True, "completeness_reason": None, "pages_fetched": 1,
    }
    coordinator.async_set_updated_data(previous)
    url = "https://api.setlist.fm/rest/1.0/user/blabla/attended"
    aioclient_mock.get(f"{url}?p=1", json={
        "setlist": [{"id": "new", "eventDate": "01-01-2026"}],
        "total": 2, "page": 1, "itemsPerPage": 1,
    })
    aioclient_mock.get(f"{url}?p=2", status=status)
    await coordinator.async_refresh()
    assert coordinator.data is previous
    assert not coordinator.last_update_success
    assert coordinator.last_exception is not None


@pytest.mark.parametrize("status", [401, 403])
async def test_coordinator_auth_failure(hass, aioclient_mock, status):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERID: "blabla", CONF_API_KEY: "secret"}
    )
    coordinator = SetlistFmCoordinator(hass, entry)
    aioclient_mock.get(
        "https://api.setlist.fm/rest/1.0/user/blabla/attended?p=1", status=status
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_success_timestamp_reads_failures_and_recovery(
    hass, entry, attendance, freezer
):
    coordinator = SetlistFmCoordinator(hass, entry)
    sensor = SetlistFmConcertsSensor(coordinator, entry)
    diagnostic = SetlistFmLastUpdateSensor(coordinator, entry)
    assert diagnostic.native_value is None
    with patch.object(coordinator.client, "async_get_attendance", return_value=attendance) as fetch:
        freezer.move_to("2026-02-01T12:00:00+00:00")
        await coordinator.async_manual_refresh()
        original = dt_util.utcnow()
        assert original.tzinfo is not None
        assert diagnostic.native_value == original
        freezer.tick(120)
        for _ in range(3):
            assert sensor.extra_state_attributes["last_updated"] == original
            assert diagnostic.native_value == original
        fetch.side_effect = SetlistFmConnectionError("offline")
        with pytest.raises(HomeAssistantError):
            await coordinator.async_manual_refresh()
        assert sensor.extra_state_attributes["last_updated"] == original
        assert diagnostic.native_value == original
        freezer.tick(120)
        fetch.side_effect = None
        await coordinator.async_manual_refresh()
        assert sensor.extra_state_attributes["last_updated"] == dt_util.utcnow()
        assert diagnostic.native_value == dt_util.utcnow()
        assert diagnostic.native_value > original
        assert "last_error" not in diagnostic.extra_state_attributes


async def test_later_page_failure_does_not_timestamp(hass, entry, aioclient_mock, freezer):
    coordinator = SetlistFmCoordinator(hass, entry)
    url = "https://api.setlist.fm/rest/1.0/user/blabla/attended"
    aioclient_mock.get(f"{url}?p=1", json={
        "setlist": [], "total": 0, "page": 1, "itemsPerPage": 20,
    })
    await coordinator.async_manual_refresh()
    timestamp = coordinator.last_successful_update
    snapshot = coordinator.data
    freezer.tick(120)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{url}?p=1", json={
        "setlist": [{"id": "one", "eventDate": "01-01-2026"}],
        "total": 2, "page": 1, "itemsPerPage": 1,
    })
    aioclient_mock.get(f"{url}?p=2", status=500)
    with pytest.raises(HomeAssistantError):
        await coordinator.async_manual_refresh()
    assert coordinator.last_successful_update == timestamp
    assert coordinator.data is snapshot


async def test_cancellation_and_shutdown_are_not_success(hass, entry, attendance):
    coordinator = SetlistFmCoordinator(hass, entry)
    started = asyncio.Event()

    async def fetch():
        started.set()
        await asyncio.Event().wait()

    with patch.object(
        coordinator.client, "async_get_attendance", side_effect=fetch
    ):
        task = asyncio.create_task(coordinator.async_manual_refresh())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert coordinator.last_successful_update is None
    with patch.object(coordinator.client, "async_get_attendance", return_value=attendance) as fetch:
        await coordinator.async_manual_refresh()
        assert fetch.await_count == 1
        await coordinator.async_shutdown()
        with pytest.raises(HomeAssistantError):
            await coordinator.async_manual_refresh()
        assert fetch.await_count == 1


async def test_manual_refresh_preserves_client_cooldown(hass, entry, aioclient_mock):
    coordinator = SetlistFmCoordinator(hass, entry)
    aioclient_mock.get(
        "https://api.setlist.fm/rest/1.0/user/blabla/attended?p=1",
        status=429, headers={"Retry-After": "120"},
    )
    for _ in range(2):
        with pytest.raises(HomeAssistantError):
            await coordinator.async_manual_refresh()
    assert aioclient_mock.call_count == 1


async def test_initial_refresh_retry_retains_cooldown(hass, aioclient_mock):
    """A new coordinator after failed setup must honor the previous cooldown."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERID: "blabla", CONF_API_KEY: "secret"},
        state=ConfigEntryState.SETUP_IN_PROGRESS,
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(
        "https://api.setlist.fm/rest/1.0/user/blabla/attended?p=1",
        status=429, headers={"Retry-After": "3600"},
    )
    token = current_entry.set(entry)
    try:
        first = SetlistFmCoordinator(hass, entry)
        with pytest.raises(ConfigEntryNotReady):
            await first.async_config_entry_first_refresh()
        assert first._unsub_refresh is None
        assert first.last_exception.retry_after == 3600
        second = SetlistFmCoordinator(hass, entry)
        assert second.client is not first.client
        with pytest.raises(ConfigEntryNotReady):
            await second.async_config_entry_first_refresh()
        assert second._unsub_refresh is None
        assert aioclient_mock.call_count == 1
        await api.sleep(3600)
        third = SetlistFmCoordinator(hass, entry)
        with pytest.raises(ConfigEntryNotReady):
            await third.async_config_entry_first_refresh()
        assert aioclient_mock.call_count == 2
    finally:
        current_entry.reset(token)


async def test_coordinator_inherits_validation_cooldown(hass, aioclient_mock):
    """Flow and coordinator clients use one shared credential deadline."""
    data = {CONF_USERID: " Blabla ", CONF_API_KEY: "secret"}
    aioclient_mock.get(
        "https://api.setlist.fm/rest/1.0/user/blabla/attended?p=1",
        status=429, headers={"Retry-After": "3600"},
    )
    with pytest.raises(api.SetlistFmRateLimitError):
        await validate_input(hass, data)
    coordinator = SetlistFmCoordinator(
        hass, MockConfigEntry(domain=DOMAIN, data=data)
    )
    with pytest.raises(UpdateFailed, match="3600 seconds"):
        await coordinator._async_update_data()
    assert aioclient_mock.call_count == 1

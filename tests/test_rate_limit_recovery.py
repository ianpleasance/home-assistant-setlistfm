"""Exercise recovery through HA's automatic timer, never a manual recovery call."""

import asyncio
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed_exact

from custom_components.setlistfm import SetlistFmCoordinator
from custom_components.setlistfm.api import (
    SetlistFmAuthError,
    SetlistFmConnectionError,
    SetlistFmRateLimitError,
)
from custom_components.setlistfm.const import CONF_REFRESH_PERIOD, DOMAIN
from tests.test_lifecycle import entity_id, load, refresh


def next_delay(hass, coordinator):
    """Read the actual HA-owned timer, not a proposed interval."""
    return coordinator._unsub_refresh.__self__.when() - hass.loop.time()


@pytest.mark.parametrize("delay", [60, 3600, 86400])
@pytest.mark.parametrize("trigger", ["scheduled", "manual"])
async def test_loaded_entry_recovers_automatically(
    hass, entry, mock_attendance, recovery_clock, delay, trigger,
):
    await load(hass, entry)
    coordinator = entry.runtime_data
    initial_timestamp = coordinator.last_successful_update
    mock_attendance.side_effect = SetlistFmRateLimitError(delay)
    if trigger == "scheduled":
        await recovery_clock(21601)
    else:
        with pytest.raises(HomeAssistantError):
            await refresh(hass)
    assert mock_attendance.await_count == 2
    assert not coordinator.last_update_success
    for suffix in ("concerts", "total_concerts", "next_concert", "last_update"):
        assert hass.states.get(entity_id(hass, entry, suffix)).state == "unavailable"
    assert coordinator.last_successful_update == initial_timestamp
    assert coordinator.update_interval == timedelta(hours=6)
    assert delay <= next_delay(hass, coordinator) <= delay + 2
    assert coordinator.last_exception.retry_after == delay

    mock_attendance.side_effect = None
    await recovery_clock(delay - 0.01)
    assert mock_attendance.await_count == 2
    await recovery_clock(2.01)
    assert mock_attendance.await_count == 3
    assert coordinator.last_update_success
    assert coordinator.last_exception is None
    assert coordinator.last_successful_update > initial_timestamp
    for suffix in ("concerts", "total_concerts", "next_concert", "last_update"):
        assert hass.states.get(entity_id(hass, entry, suffix)).state != "unavailable"
    assert hass.states.get(entity_id(hass, entry, "total_concerts")).state == "4"
    assert 21599 <= next_delay(hass, coordinator) <= 21601
    await recovery_clock(10)
    assert mock_attendance.await_count == 3
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert coordinator._unsub_refresh is None
    assert hass.services.has_service(DOMAIN, "refresh")


@pytest.mark.parametrize("cleanup", ["unload", "shutdown", "reload", "disable", "stop"])
async def test_pending_recovery_cleanup(
    hass, entry, mock_attendance, recovery_clock, cleanup,
):
    await load(hass, entry)
    coordinator = entry.runtime_data
    mock_attendance.side_effect = SetlistFmRateLimitError(60)
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    timer = coordinator._unsub_refresh.__self__
    mock_attendance.side_effect = None
    if cleanup == "unload":
        assert await hass.config_entries.async_unload(entry.entry_id)
    elif cleanup == "shutdown":
        await coordinator.async_shutdown()
    elif cleanup == "stop":
        await hass.async_stop()
    else:
        if cleanup == "reload":
            hass.config_entries.async_update_entry(
                entry, options={CONF_REFRESH_PERIOD: 12}
            )
        else:
            hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
        await hass.async_block_till_done()
        assert entry.runtime_data is not coordinator
        if cleanup == "reload":
            assert entry.runtime_data.update_interval == timedelta(hours=12)
        else:
            assert entry.runtime_data._unsub_refresh is None
    assert timer.cancelled()
    assert coordinator._unsub_refresh is None
    calls = mock_attendance.await_count
    await recovery_clock(100)
    assert mock_attendance.await_count == calls


@pytest.mark.parametrize("disabled", ["listeners", "preference", "interval", "zero_interval"])
async def test_no_automatic_recovery_when_polling_disabled(
    hass, entry, mock_attendance, recovery_clock, disabled,
):
    if disabled == "preference":
        hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
    coordinator = SetlistFmCoordinator(hass, entry)
    remove_listener = coordinator.async_add_listener(lambda: None)
    await coordinator.async_manual_refresh()
    if disabled == "interval":
        coordinator.update_interval = None
    elif disabled == "zero_interval":
        coordinator.update_interval = timedelta(0)
    mock_attendance.side_effect = SetlistFmRateLimitError(60)
    with pytest.raises(HomeAssistantError):
        await coordinator.async_manual_refresh()
    if disabled == "listeners":
        timer = coordinator._unsub_refresh.__self__
        remove_listener()
        assert timer.cancelled()
    assert coordinator._unsub_refresh is None
    mock_attendance.side_effect = None
    await recovery_clock(100)
    assert mock_attendance.await_count == 2
    if disabled != "listeners":
        remove_listener()
    await coordinator.async_shutdown()


async def test_subsecond_remaining_delay_survives_ha_timer_rounding(
    hass, entry, mock_attendance, recovery_clock, freezer,
):
    await load(hass, entry)
    coordinator = entry.runtime_data
    coordinator._microsecond = 0.05
    freezer.tick(1.99 - hass.loop.time() % 1)
    mock_attendance.side_effect = SetlistFmRateLimitError(0.01)
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    assert 0.01 <= next_delay(hass, coordinator) <= 1.51
    mock_attendance.side_effect = None
    await recovery_clock(0.009)
    assert mock_attendance.await_count == 2
    await recovery_clock(0.1)
    assert mock_attendance.await_count == 3
    assert coordinator.last_update_success
    await recovery_clock(2)
    assert mock_attendance.await_count == 3


@pytest.mark.parametrize("auth", [False, True])
async def test_recovery_non_rate_error_keeps_normal_error_behavior(
    hass, entry, mock_attendance, recovery_clock, auth,
):
    await load(hass, entry)
    coordinator = entry.runtime_data
    mock_attendance.side_effect = SetlistFmRateLimitError(60)
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    mock_attendance.side_effect = (
        SetlistFmAuthError("rejected") if auth else SetlistFmConnectionError("offline")
    )
    with patch.object(entry, "async_start_reauth") as reauth:
        await recovery_clock(62)
    assert mock_attendance.await_count == 3
    assert not coordinator.last_update_success
    if auth:
        reauth.assert_called_once()
        assert coordinator._unsub_refresh is None
    else:
        reauth.assert_not_called()
        assert 21599 <= next_delay(hass, coordinator) <= 21601
    await recovery_clock(100)
    assert mock_attendance.await_count == 3


async def test_automatic_recovery_serializes_with_manual_result(
    hass, entry, mock_attendance, attendance, recovery_clock, freezer,
):
    await load(hass, entry)
    coordinator = entry.runtime_data
    mock_attendance.side_effect = SetlistFmRateLimitError(60)
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    started = asyncio.Event()
    release = asyncio.Event()
    calls = active = maximum = 0

    async def fetch():
        nonlocal calls, active, maximum
        calls += 1
        active += 1
        maximum = max(maximum, active)
        try:
            if calls == 1:
                started.set()
                await release.wait()
                return attendance
            raise SetlistFmConnectionError("manual operation failed")
        finally:
            active -= 1

    mock_attendance.side_effect = fetch
    freezer.tick(62)
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await started.wait()
    manual = asyncio.create_task(coordinator.async_manual_refresh())
    await asyncio.sleep(0)
    assert not manual.done()
    release.set()
    with pytest.raises(HomeAssistantError, match="manual operation failed"):
        await manual
    await hass.async_block_till_done(wait_background_tasks=True)
    assert calls == 2 and maximum == 1
    assert not coordinator.last_update_success
    assert 21599 <= next_delay(hass, coordinator) <= 21601


@pytest.mark.parametrize("unload", [False, True])
async def test_shutdown_during_recovery_does_not_rearm_timer(
    hass, entry, mock_attendance, attendance, recovery_clock, freezer, unload,
):
    await load(hass, entry)
    coordinator = entry.runtime_data
    mock_attendance.side_effect = SetlistFmRateLimitError(60)
    with pytest.raises(HomeAssistantError):
        await refresh(hass)
    started = asyncio.Event()
    release = asyncio.Event()
    cancelled = asyncio.Event()

    async def fetch():
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return attendance

    mock_attendance.side_effect = fetch
    freezer.tick(62)
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await started.wait()
    if unload:
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert cancelled.is_set()
    else:
        await coordinator.async_shutdown()
    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator._unsub_refresh is None
    await recovery_clock(21602)
    assert mock_attendance.await_count == 3

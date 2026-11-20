"""HA-owned quota state remains effective across client and coordinator lifetimes."""
import asyncio
from hashlib import sha256
from unittest.mock import patch

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.setlistfm import api
from custom_components.setlistfm.api import (
    RequestStateStore,
    SetlistFmClient,
    SetlistFmConnectionError,
    SetlistFmRateLimitError,
)
from custom_components.setlistfm.client import DATA_REQUEST_STATES, async_create_client
from custom_components.setlistfm.const import DOMAIN

URL = "https://api.setlist.fm/rest/1.0/user/blabla/attended?p=1"
OTHER_URL = "https://api.setlist.fm/rest/1.0/user/other/attended?p=1"
EMPTY = {"total": 0, "page": 1, "itemsPerPage": 20, "setlist": []}


async def test_injected_state_survives_fresh_clients(hass, aioclient_mock):
    """Standalone clients may opt into shared state without depending on HA."""
    aioclient_mock.get(URL, status=429, headers={"Retry-After": "3600"})
    states = RequestStateStore()
    session = async_get_clientsession(hass)
    for _ in range(2):
        client = SetlistFmClient(session, "key", "blabla", request_states=states)
        with pytest.raises(SetlistFmRateLimitError):
            await client.async_validate_access()
    assert aioclient_mock.call_count == 1


async def test_factory_shares_deadlines_by_key_not_username(hass, aioclient_mock):
    aioclient_mock.get(URL, status=429, headers={"Retry-After": "3600"})
    aioclient_mock.get(OTHER_URL, json=EMPTY)
    first = async_create_client(hass, "sensitive-key", " BlaBla ")
    with pytest.raises(SetlistFmRateLimitError):
        await first.async_validate_access()
    second = async_create_client(hass, "sensitive-key", "other")
    assert second is not first
    with pytest.raises(SetlistFmRateLimitError) as error:
        await second.async_validate_access()
    assert error.value.retry_after == 3600
    assert aioclient_mock.call_count == 1

    registry = hass.data[DATA_REQUEST_STATES]
    assert list(registry._states) == [sha256(b"sensitive-key").digest()]
    assert "sensitive-key" not in repr(registry._states)
    assert "blabla" not in repr(registry._states)
    assert DOMAIN not in hass.data

    await api.sleep(3600)
    third = async_create_client(hass, "sensitive-key", "other")
    await third.async_validate_access()
    assert aioclient_mock.call_count == 2
    assert hass.data[DATA_REQUEST_STATES] is registry


async def test_distinct_credentials_do_not_share_cooldown(hass, aioclient_mock):
    """Keys remain case-sensitive and independent even for the same username."""
    aioclient_mock.get(URL, status=429, headers={"Retry-After": "3600"})
    for key in ("CaseSensitive", "casesensitive"):
        with pytest.raises(SetlistFmRateLimitError):
            await async_create_client(hass, key, "blabla").async_validate_access()
    assert aioclient_mock.call_count == 2
    with pytest.raises(SetlistFmRateLimitError):
        await async_create_client(hass, "CaseSensitive", "blabla").async_validate_access()
    assert aioclient_mock.call_count == 2


async def test_factory_shares_request_pacing(hass, aioclient_mock, api_clock):
    aioclient_mock.get(URL, json=EMPTY)
    for _ in range(2):
        await async_create_client(hass, "key", "blabla").async_validate_access()
    assert aioclient_mock.call_count == 2
    assert api_clock == [0, 1]


async def test_capacity_never_evicts_live_cooldowns(hass, aioclient_mock):
    """Saturation fails explicitly instead of resetting a protected quota."""
    aioclient_mock.get(URL, status=429, headers={"Retry-After": "3600"})
    aioclient_mock.get(OTHER_URL, json=EMPTY)
    with patch("custom_components.setlistfm.api.MAX_REQUEST_STATES", 2):
        for key in ("first", "second"):
            with pytest.raises(SetlistFmRateLimitError):
                await async_create_client(hass, key, "blabla").async_validate_access()
        with pytest.raises(SetlistFmConnectionError, match="Too many active"):
            await async_create_client(hass, "third", "blabla").async_validate_access()
        with pytest.raises(SetlistFmRateLimitError):
            await async_create_client(hass, "first", "blabla").async_validate_access()
        assert aioclient_mock.call_count == 2
        registry = hass.data[DATA_REQUEST_STATES]
        assert len(registry._states) == 2
        await api.sleep(3600)
        await async_create_client(hass, "third", "other").async_validate_access()
        assert aioclient_mock.call_count == 3
        assert len(registry._states) == 1


async def test_old_client_rejoins_registry_after_expired_state_eviction(
    hass, aioclient_mock
):
    """An older client must not keep detached state that bypasses a newer deadline."""
    aioclient_mock.get(URL, status=429, headers={"Retry-After": "3600"})
    aioclient_mock.get(OTHER_URL, json=EMPTY)
    old = async_create_client(hass, "first", "blabla")
    with pytest.raises(SetlistFmRateLimitError):
        await old.async_validate_access()
    await api.sleep(3600)
    await async_create_client(hass, "second", "other").async_validate_access()
    registry = hass.data[DATA_REQUEST_STATES]
    assert sha256(b"first").digest() not in registry._states
    with pytest.raises(SetlistFmRateLimitError):
        await old.async_validate_access()
    with pytest.raises(SetlistFmRateLimitError):
        await async_create_client(hass, "first", "blabla").async_validate_access()
    assert aioclient_mock.call_count == 3


async def test_active_state_reservations_survive_expiry_and_cancellation():
    """Protect holders and lock waiters; release reservations even on cancellation."""
    store = RequestStateStore()
    with patch("custom_components.setlistfm.api.MAX_REQUEST_STATES", 1):
        with store.request_state(b"first") as first:
            with store.request_state(b"first") as waiting:
                assert first is waiting
                assert first.users == 2
                await api.sleep(3600)
                with pytest.raises(SetlistFmConnectionError, match="Too many active"):
                    with store.request_state(b"other"):
                        pytest.fail("Active state must not be evicted")
            assert first.users == 1
        assert first.users == 0
        with pytest.raises(asyncio.CancelledError):
            with store.request_state(b"other"):
                raise asyncio.CancelledError
        with store.request_state(b"new") as new:
            assert new.users == 1
        assert len(store._states) == 1

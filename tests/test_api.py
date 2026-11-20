"""Request bounds, pagination integrity, and attendance coverage contracts."""
import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.setlistfm import api
from custom_components.setlistfm.api import (
    MAX_ATTEMPTS,
    MAX_PAGES,
    REQUEST_TIMEOUT,
    SetlistFmAuthError,
    SetlistFmClient,
    SetlistFmConnectionError,
    SetlistFmRateLimitError,
    SetlistFmResponseError,
    _retry_after,
)

URL = "https://api.setlist.fm/rest/1.0/user/blabla/attended"


def concert(index):
    return {"id": str(index), "eventDate": "01-01-2026"}


def page(number=1, total=1, size=20):
    return {
        "setlist": [
            concert(index)
            for index in range((number - 1) * size, min(number * size, total))
        ],
        "total": total, "page": number, "itemsPerPage": size,
    }


def mock_session(*responses):
    """Mock only HTTP boundaries, not Home Assistant."""
    session = MagicMock(spec=aiohttp.ClientSession)
    contexts = []
    for response in responses:
        context = MagicMock()
        if isinstance(response, BaseException):
            context.__aenter__ = AsyncMock(side_effect=response)
        else:
            status, payload, headers = response
            result = MagicMock(status=status, headers=headers)
            result.json = AsyncMock(return_value=payload)
            context.__aenter__ = AsyncMock(return_value=result)
        context.__aexit__ = AsyncMock(return_value=False)
        contexts.append(context)
    session.get.side_effect = contexts
    return session


async def test_three_pages(hass, aioclient_mock, api_clock):
    for number in (1, 2, 3):
        aioclient_mock.get(f"{URL}?p={number}", json=page(number, total=42))
    client = SetlistFmClient(async_get_clientsession(hass), "secret", " BlaBla ")
    data = await client.async_get_attendance()
    assert [item["id"] for item in data["concerts"]] == [str(i) for i in range(42)]
    assert data | {"concerts": []} == {
        "concerts": [], "total": 42, "fetched_count": 42, "skipped_count": 0,
        "complete": True, "completeness_reason": None, "pages_fetched": 3,
    }
    assert aioclient_mock.call_count == 3
    assert api_clock == [0, 1, 1]


@pytest.mark.parametrize("size", [0, 20])
async def test_explicit_empty_account(hass, aioclient_mock, size):
    aioclient_mock.get(f"{URL}?p=1", json=page(total=0, size=size))
    data = await SetlistFmClient(
        async_get_clientsession(hass), "secret", "blabla"
    ).async_get_attendance()
    assert data["total"] == data["fetched_count"] == 0
    assert data["complete"]
    assert data["pages_fetched"] == 1


async def test_ambiguous_no_attendance(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}?p=1", status=404)
    client = SetlistFmClient(async_get_clientsession(hass), "secret", "blabla")
    await client.async_validate_access()
    data = await client.async_get_attendance()
    assert data["concerts"] == []
    assert data["total"] is None
    assert not data["complete"]
    assert data["completeness_reason"] == "attendance_not_found"


@pytest.mark.parametrize(
    "payload",
    [
        {}, [], None,
        {**page(), "total": "1"},
        {**page(), "total": True},
        {**page(), "total": -1},
        {**page(), "itemsPerPage": 0},
        {**page(), "itemsPerPage": "20"},
        {**page(), "page": 2},
        {**page(), "setlist": {}},
        {**page(), "setlist": []},
        {**page(), "total": MAX_PAGES * 20 + 1},
    ],
)
async def test_malformed_pages_fail(hass, aioclient_mock, payload):
    aioclient_mock.get(f"{URL}?p=1", json=payload)
    with pytest.raises(SetlistFmResponseError):
        await SetlistFmClient(
            async_get_clientsession(hass), "secret", "blabla"
        ).async_get_attendance()
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    "second",
    [
        page(1, total=3, size=2),
        page(2, total=4, size=2),
        page(2, total=3, size=3),
        {**page(2, total=3, size=2), "setlist": []},
        {**page(2, total=3, size=2), "setlist": [concert(0)]},
    ],
)
async def test_inconsistent_or_repeated_pages(hass, aioclient_mock, second):
    aioclient_mock.get(f"{URL}?p=1", json=page(total=3, size=2))
    aioclient_mock.get(f"{URL}?p=2", json=second)
    with pytest.raises(SetlistFmResponseError):
        await SetlistFmClient(
            async_get_clientsession(hass), "secret", "blabla"
        ).async_get_attendance()
    assert aioclient_mock.call_count == 2


async def test_duplicate_within_page_fails(hass, aioclient_mock):
    aioclient_mock.get(
        f"{URL}?p=1", json={**page(total=2), "setlist": [concert(0), concert(0)]}
    )
    with pytest.raises(SetlistFmResponseError, match="Repeated"):
        await SetlistFmClient(
            async_get_clientsession(hass), "secret", "blabla"
        ).async_get_attendance()


async def test_missing_identifiers_are_not_treated_as_duplicates(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}?p=1", json={
        **page(total=3),
        "setlist": [concert(""), concert(""), concert("valid")],
    })
    data = await SetlistFmClient(
        async_get_clientsession(hass), "secret", "blabla"
    ).async_get_attendance()
    assert [item["id"] for item in data["concerts"]] == ["valid"]
    assert data["skipped_count"] == 2
    assert not data["complete"]


@pytest.mark.parametrize("invalid_date", [
    "not-a-date", "1-1-2026", " 1-01-2026", "01-01-2026 ",
])
async def test_invalid_individual_records_do_not_erase_valid_concerts(
    hass, aioclient_mock, caplog, invalid_date,
):
    records = [
        concert(0), {**concert(1), "eventDate": invalid_date},
        None, {"eventDate": "01-01-2026"},
        {**concert(4), "venue": "invalid"},
    ]
    aioclient_mock.get(f"{URL}?p=1", json={**page(total=5), "setlist": records})
    data = await SetlistFmClient(
        async_get_clientsession(hass), "secret", "blabla"
    ).async_get_attendance()
    assert [item["id"] for item in data["concerts"]] == ["0", "4"]
    assert data["total"] == 5
    assert data["fetched_count"] == 2
    assert data["skipped_count"] == 3
    assert not data["complete"]
    assert data["completeness_reason"] == "invalid_records"
    assert "skipped 3 records, repaired optional fields in 1 records" in caplog.text
    assert "secret" not in caplog.text


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_errors_are_not_retried(status):
    session = mock_session((status, {}, {}))
    with pytest.raises(SetlistFmAuthError):
        await SetlistFmClient(session, "secret", "blabla").async_validate_access()
    assert session.get.call_count == 1


@pytest.mark.parametrize(
    "failure",
    [TimeoutError(), aiohttp.ClientConnectionError(), (503, {}, {}), (502, {}, {})],
)
async def test_transient_failure_recovers(failure, api_clock):
    session = mock_session(failure, (200, page(), {}))
    await SetlistFmClient(session, "secret", "blabla").async_validate_access()
    assert session.get.call_count == 2
    assert api_clock == [0, 2, 0]
    for call in session.get.call_args_list:
        assert call.kwargs["timeout"] is REQUEST_TIMEOUT
        assert call.kwargs["timeout"].total == 20
        assert call.kwargs["headers"]["x-api-key"] == "secret"


@pytest.mark.parametrize("failure", [TimeoutError(), (500, {}, {})])
async def test_transient_retry_exhaustion(failure, api_clock):
    session = mock_session(*([failure] * MAX_ATTEMPTS))
    with pytest.raises(SetlistFmConnectionError):
        await SetlistFmClient(session, "secret", "blabla").async_validate_access()
    assert session.get.call_count == MAX_ATTEMPTS
    assert sum(api_clock) == 6


async def test_short_retry_after_recovers(api_clock):
    session = mock_session((429, {}, {"Retry-After": "5"}), (200, page(), {}))
    await SetlistFmClient(session, "secret", "blabla").async_validate_access()
    assert api_clock == [0, 5, 0]
    assert session.get.call_count == 2


async def test_rate_limit_exhaustion(api_clock):
    session = mock_session(*([(429, {}, {"Retry-After": "0"})] * MAX_ATTEMPTS))
    client = SetlistFmClient(session, "secret", "blabla")
    with pytest.raises(SetlistFmRateLimitError):
        await client.async_get_attendance()
    assert session.get.call_count == MAX_ATTEMPTS
    assert sum(api_clock) == 6
    with pytest.raises(SetlistFmRateLimitError):
        await client.async_get_attendance()
    assert session.get.call_count == MAX_ATTEMPTS


@pytest.mark.parametrize("status", [429, 503])
async def test_rate_limit_cooldown_expires(status, caplog):
    caplog.set_level(logging.DEBUG, logger="custom_components.setlistfm.api")
    secret = "private-api-key"
    userid = "private-username"
    session = mock_session(
        (200, page(total=2, size=1), {}),
        (status, {"private": "private-payload"}, {
            "Retry-After": "60", "private-header": secret,
        }),
        (200, page(total=2, size=1), {}),
        (200, page(2, total=2, size=1), {}),
    )
    client = SetlistFmClient(session, secret, userid)
    with pytest.raises(SetlistFmRateLimitError):
        await client.async_get_attendance()
    assert session.get.call_count == 2
    await api.sleep(39)
    with pytest.raises(SetlistFmRateLimitError, match="21 seconds"):
        await client.async_get_attendance()
    assert session.get.call_count == 2
    await api.sleep(21)
    data = await client.async_get_attendance()
    assert data["complete"]
    assert data["fetched_count"] == data["total"] == 2
    assert data["pages_fetched"] == 2
    assert session.get.call_count == 4
    records = [
        record for record in caplog.records
        if record.name == "custom_components.setlistfm.api"
    ]
    assert [record.getMessage() for record in records] == [
        f"Attendance page 2 received HTTP {status}; backoff 60.0 seconds",
        "Attendance page 1 deferred by shared cooldown before HTTP; 21 seconds remaining",
    ]
    assert all(record.levelno == logging.DEBUG for record in records)
    for private in (secret, userid, "private-header", "private-payload", api.BASE_URL):
        assert private not in caplog.text


@pytest.mark.parametrize("header,delay", [(None, 60), ("invalid", 60), ("3600", 3600)])
async def test_long_or_unknown_quota_does_not_spin(header, delay, api_clock):
    headers = {} if header is None else {"Retry-After": header}
    session = mock_session((429, {}, headers))
    client = SetlistFmClient(session, "secret", "blabla")
    for _ in range(2):
        with pytest.raises(SetlistFmRateLimitError) as error:
            await client.async_get_attendance()
        assert error.value.retry_after == delay
    assert session.get.call_count == 1
    assert sum(api_clock) == 0


@pytest.mark.parametrize("value", [None, "", "-1", "0.5", "NaN", "tomorrow"])
def test_invalid_retry_after(value):
    assert _retry_after(value) is None


def test_retry_after_http_date():
    now = datetime.now(timezone.utc)
    delay = _retry_after(format_datetime(now + timedelta(seconds=20), usegmt=True))
    assert delay is not None and 18 <= delay <= 20
    assert _retry_after(format_datetime(now - timedelta(seconds=20), usegmt=True)) is None


async def test_http_date_retry_and_service_cooldown(api_clock):
    header = format_datetime(datetime.now(timezone.utc) + timedelta(hours=1), usegmt=True)
    session = mock_session((503, {}, {"Retry-After": header}))
    with pytest.raises(SetlistFmRateLimitError) as error:
        await SetlistFmClient(session, "secret", "blabla").async_validate_access()
    assert error.value.retry_after >= 3598
    assert sum(api_clock) == 0


async def test_cancellation_is_not_retried():
    session = mock_session(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await SetlistFmClient(session, "secret", "blabla").async_get_attendance()
    assert session.get.call_count == 1


async def test_cancellation_during_backoff():
    session = mock_session((503, {}, {}))
    with patch(
        "custom_components.setlistfm.api.sleep",
        side_effect=[None, asyncio.CancelledError()],
    ):
        with pytest.raises(asyncio.CancelledError):
            await SetlistFmClient(session, "secret", "blabla").async_get_attendance()
    assert session.get.call_count == 1


async def test_cancellation_does_not_clear_known_rate_limit():
    session = mock_session((429, {}, {"Retry-After": "5"}))
    client = SetlistFmClient(session, "secret", "blabla")
    with patch(
        "custom_components.setlistfm.api.sleep",
        side_effect=[None, asyncio.CancelledError()],
    ):
        with pytest.raises(asyncio.CancelledError):
            await client.async_get_attendance()
    with pytest.raises(SetlistFmRateLimitError) as error:
        await client.async_get_attendance()
    assert error.value.retry_after == 5
    assert session.get.call_count == 1


async def test_invalid_json(hass, aioclient_mock):
    aioclient_mock.get(
        f"{URL}?p=1", text="not-json", headers={"Content-Type": "application/json"}
    )
    with pytest.raises(SetlistFmResponseError, match="invalid JSON"):
        await SetlistFmClient(
            async_get_clientsession(hass), "secret", "blabla"
        ).async_get_attendance()
    assert aioclient_mock.call_count == 1


async def test_wrong_content_type():
    session = mock_session((200, page(), {}))
    session.get.side_effect = None
    response = session.get.return_value.__aenter__.return_value
    response.status = 200
    response.json.side_effect = aiohttp.ContentTypeError(
        request_info=MagicMock(), history=(), message="Invalid content type"
    )
    with pytest.raises(SetlistFmResponseError, match="invalid JSON"):
        await SetlistFmClient(session, "secret", "blabla").async_get_attendance()
    assert session.get.call_count == 1


async def test_pagination_safety_bound(hass, aioclient_mock):
    aioclient_mock.get(
        f"{URL}?p=1", json=page(total=MAX_PAGES * 20 + 1)
    )
    with pytest.raises(SetlistFmResponseError, match="safety bound"):
        await SetlistFmClient(
            async_get_clientsession(hass), "secret", "blabla"
        ).async_get_attendance()
    assert aioclient_mock.call_count == 1


async def test_no_assumed_thousand_concert_cap(hass, aioclient_mock):
    for number in range(1, 52):
        aioclient_mock.get(f"{URL}?p={number}", json=page(number, total=1001))
    data = await SetlistFmClient(
        async_get_clientsession(hass), "secret", "blabla"
    ).async_get_attendance()
    assert data["fetched_count"] == data["total"] == 1001
    assert data["complete"]
    assert data["pages_fetched"] == 51
    assert aioclient_mock.call_count == 51


async def test_unexpected_programming_errors_propagate():
    session = mock_session(TypeError("programming error"))
    with pytest.raises(TypeError, match="programming error"):
        await SetlistFmClient(session, "secret", "blabla").async_validate_access()
    assert session.get.call_count == 1


async def test_reserved_characters_in_username_are_path_encoded(hass, aioclient_mock):
    aioclient_mock.get(
        "https://api.setlist.fm/rest/1.0/user/name%2Fpart/attended?p=1",
        json=page(total=0),
    )
    await SetlistFmClient(
        async_get_clientsession(hass), "secret", " Name/Part "
    ).async_validate_access()
    assert aioclient_mock.call_count == 1

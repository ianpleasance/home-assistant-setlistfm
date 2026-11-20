"""Real loopback transport fixtures, isolated from the fast mocked tests."""

from contextlib import AsyncExitStack

import aiohttp
import pytest
from pytest_socket import socket_allow_hosts

from custom_components.setlistfm import api
from devtools.setlistfm_mock import Account, MockSetlistApi


@pytest.fixture(autouse=True)
def loopback_only(socket_enabled):
    """Permit only loopback connections, even if a test forgets the URL seam."""
    socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)


@pytest.fixture
async def setlist_server(monkeypatch):
    """Start independent servers and redirect only subsequently created clients."""
    async with AsyncExitStack() as stack:
        async def start(accounts=None, **kwargs):
            server = MockSetlistApi(
                [Account("demo")] if accounts is None else accounts, **kwargs
            )
            await stack.enter_async_context(server)
            monkeypatch.setattr(api, "BASE_URL", server.base_url)
            return server

        yield start


@pytest.fixture
async def http_session():
    """No aioclient_mock: bytes travel over TCP through aiohttp on both sides."""
    async with aiohttp.ClientSession() as session:
        yield session

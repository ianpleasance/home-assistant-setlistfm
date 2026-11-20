"""Smoke the documented foreground command in an isolated subprocess."""

import asyncio
import signal
import sys

import pytest


@pytest.mark.parametrize("scenario", ["mixed", "auth-403"])
async def test_foreground_cli_and_clean_interrupt(http_session, unused_tcp_port, scenario):
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-u", "-m", "devtools.setlistfm_mock",
        "--scenario", scenario, "--port", str(unused_tcp_port),
        "--api-key", "mock-cli-key",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(10):
            while True:
                line = await process.stdout.readline()
                assert line, (await process.stderr.read()).decode()
                if b"Running on http://127.0.0.1:" in line:
                    break
        assert process.returncode is None
        async with http_session.get(
            f"http://127.0.0.1:{unused_tcp_port}/rest/1.0/user/demo/attended?p=1",
            headers={"Accept": "application/json", "x-api-key": "mock-cli-key"},
        ) as response:
            assert response.status == (200 if scenario == "mixed" else 403)
            if scenario == "mixed":
                data = await response.json()
                assert "set" in data["setlist"][0]
                assert "sets" in data["setlist"][1]
    finally:
        if process.returncode is None:
            process.send_signal(signal.SIGINT)
        try:
            async with asyncio.timeout(10):
                _, stderr = await process.communicate()
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise
    assert process.returncode == 0, stderr.decode()
    assert not stderr

"""Run in the foreground with Ctrl+C cleanup; never bind a public interface."""

import argparse

from aiohttp import web

from .scenarios import SCENARIOS, make_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="baseline")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--api-key", default="mock-api-key", help="Dummy key starting with mock-")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not args.api_key.startswith("mock-"):
        parser.error("--api-key must be a dummy value starting with mock-")
    server = make_scenario(args.scenario, api_key=args.api_key)
    print(f"Scenario: {args.scenario}; fictional users: demo, empty", flush=True)
    web.run_app(
        server.app, host="127.0.0.1", port=args.port, access_log=None,
        handler_cancellation=True, shutdown_timeout=0.1,
    )


if __name__ == "__main__":
    main()

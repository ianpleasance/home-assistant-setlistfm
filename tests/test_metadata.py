"""Validate maintained locale contracts and optional dashboard examples."""
import json
from pathlib import Path
from string import Formatter

import pytest
import yaml
from homeassistant.helpers.template import Template

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "setlistfm"
LOCALES = ("da", "de", "en", "es", "fi", "fr", "it", "ja", "nl", "no", "pl", "pt", "sv")


def test_upstream_identity_and_frontend_installation_metadata():
    """Keep upstream attribution while declaring the bundled frontend dependency."""
    upstream = "https://github.com/ianpleasance/home-assistant-setlistfm"
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert manifest["documentation"] == upstream
    assert manifest["issue_tracker"] == f"{upstream}/issues"
    assert manifest["codeowners"] == ["@ianpleasance"]
    assert manifest["dependencies"] == ["frontend"]
    assert manifest["requirements"] == []
    assert manifest["integration_type"] == "service"
    hacs_url = (
        "https://my.home-assistant.io/redirect/hacs_repository/"
        "?owner=ianpleasance&repository=home-assistant-setlistfm&category=integration"
    )
    for document in ("README.md", "INSTALL.md"):
        assert hacs_url in (ROOT / document).read_text()


@pytest.mark.parametrize("locale", LOCALES)
def test_native_translations(locale):
    reference = json.loads((INTEGRATION / "strings.json").read_text())
    translated = json.loads(
        (INTEGRATION / "translations" / f"{locale}.json").read_text()
    )
    paths = [
        ("config", "step", "reauth_confirm", "title"),
        ("config", "step", "reauth_confirm", "description"),
        ("config", "step", "reauth_confirm", "data", "api_key"),
        ("config", "abort", "reauth_successful"),
        *(("config", "error", key) for key in (
            "cannot_connect", "invalid_auth", "rate_limited", "invalid_response"
        )),
        *(("entity", "sensor", key, "name") for key in (
            "concerts", "total_concerts", "unique_concert_visits", "next_concert", "last_update"
        )),
        ("entity", "button", "refresh", "name"),
        *(("exceptions", key, "message") for key in (
            "invalid_entry", "no_loaded_entries", "entry_unloaded", "refresh_failed"
        )),
    ]
    for path in paths:
        expected, actual = reference, translated
        for key in path:
            expected, actual = expected[key], actual[key]
        assert isinstance(actual, str) and actual.strip()
        assert {name for _, name, _, _ in Formatter().parse(expected) if name} == {
            name for _, name, _, _ in Formatter().parse(actual) if name
        }
        if locale == "en":
            assert actual == expected
    assert "user_not_found" not in translated["config"]["error"]


@pytest.mark.parametrize("dashboard", (
    "DASHBOARD_COMPACT.yaml", "DASHBOARD_COMPLETE.yaml",
    "DASHBOARD_DELUXE.yaml", "DASHBOARD_MOBILE.yaml",
))
async def test_dashboard_templates_without_data(hass, dashboard):
    """Optional examples must at least parse/render before entities are available."""
    document = yaml.safe_load((ROOT / dashboard).read_text())

    def check(value):
        if isinstance(value, dict):
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
        elif isinstance(value, str) and ("{{" in value or "{%" in value):
            assert isinstance(Template(value, hass).async_render(parse_result=False), str)

    check(document)

# Bundled setlist.fm cards

The integration includes four **individual cards**, inspired by the optional YAML dashboards. They use one local, dependency-free web component implementation. They do not install or replace a dashboard view.

## Add a card without YAML

1. Install/update the integration and restart Home Assistant.
2. Configure at least one setlist.fm account under **Settings > Devices & services** and allow its first refresh to finish.
3. Open a dashboard you can edit, choose **Edit dashboard > Add card > By cards** (**By card** in some versions), then find the **Community** section (or search for `setlist.fm`).
4. Pick **setlist.fm Complete**, **Compact**, **Deluxe**, or **Mobile**.
5. In the visual editor, select **Account / concerts entity**. The preview uses that account's available records. Adjust the title, filter, section limit, location and song-count options, optionally enable **Group by concert visit**, then save.

In Home Assistant 2025.1, the same picker lists these as **Custom: setlist.fm Complete** (and the other presets), without the newer Community grouping. Search for `setlist.fm` under **By card**.

No separate frontend repository, CDN, JavaScript resource configuration, or YAML copying is required. A freshly added account with no available records shows explanatory guidance instead of invented sample concerts.

| Preset | Presentation |
| --- | --- |
| Complete | Next available show, more upcoming dates, recent concerts and display-list counts |
| Compact | A small next-show highlight and a short artist/date/link recent list; venue/location details appear in the highlight |
| Deluxe | A larger featured show, detailed lists and upcoming/past counts within the available records |
| Mobile | A single-column layout with touch-sized links and controls |

All presets follow Home Assistant theme colors and typography, adapt to narrow widths, and work in masonry and sections dashboards. Wide Complete and Deluxe cards arrange lists in two columns. The editor uses labeled native controls with keyboard support. **Account details** opens the selected sensor's Home Assistant more-info dialog. Setlist links open safely in a new tab.

## Accounts, dates and limits

The selector recognizes the concerts data contract, not a `sensor.setlistfm_` naming prefix. Multiple accounts and renamed entity IDs work. If you rename an entity after saving a card, reselect it in the editor: Home Assistant does not necessarily rewrite custom-card configurations. If an account is temporarily unavailable, its saved selection is retained.

Select the **Concerts shown** sensor (previously named **Concerts**), not
**Total concerts** or **Unique concert visits**. The default label now clarifies the display-limited count;
existing entity IDs, custom names and saved card selections remain unchanged.

By default, cards use the existing `concerts` array (`date` in canonical `DD-MM-YYYY`, artist, venue, song count and URL), `last_updated`, and `last_update_success`. With grouping enabled they use `concert_visits` instead. They do not parse `concert_list` text for presentation or need new total/date entities. The next show is the **earliest upcoming record in the available list**, with today's date counted as upcoming. Date boundaries use **Home Assistant's configured time zone**, even if the browser is elsewhere.

Cards and sensors reuse one shared fetched snapshot per account. Adding cards,
opening the picker, changing card options or reading sensor attributes does not
call setlist.fm. Each account refresh uses one HTTP request per required page,
not one request per sensor or card.

The integration's **Show concerts** and **Number of concerts** options filter and cap the source lists before a card sees them. The 1-50 limit applies independently to raw performances and grouped visits. Card options can narrow those lists further but cannot recover omitted records. A section limit applies separately to the more-upcoming and recent lists, in addition to the featured next show: it counts **visits when grouping is enabled, performances otherwise**. Compact intentionally shows only one upcoming show or visit. Counts describe the available list, **not lifetime attendance**; an empty response does not prove zero attendance. Upcoming coverage is limited to future-dated setlists returned by the attended endpoint, with no separate upcoming API or guaranteed future-date window. Song counts are songs listed in a setlist, not predictions.

Unavailable data, unknown/loading states, missing entities, invalid records and failed updates have distinct messages. When the backend supplies `complete: false`, the card also warns about upstream incompleteness, including records skipped before they reached the card or an ambiguous empty/unknown-username response. This is separate from the integration's normal display filter and limit; older sensors without completeness metadata remain supported.

The card does not display raw API errors or credentials. API text is always inserted as text, never HTML. Only HTTP(S) links on `setlist.fm` or `www.setlist.fm` are accepted, and accepted HTTP URLs are upgraded to HTTPS.

## Group by concert visit

All four presets support the visual-editor toggle **Group by concert visit**
(`group_by_visit`, boolean, default `false`). Existing cards stay in individual
performance mode unless you enable it. Each grouped item shows the date, venue
and lineup with **all included artists alphabetically**, plus each performance's
own safe setlist link and song count (when song counts are enabled). Alphabetical
order is not billing order; the integration does not infer a headliner.

Grouping is done by the integration across the full validated snapshot, before
date filtering and limiting. A visit is the tuple of a canonical `DD-MM-YYYY`
date and a valid nonempty string `venue.id`. Artists at that venue on that date
are one visit. This deliberately also collapses independent same-day shows at
the same venue; festival stages with different IDs stay separate. Venue names
are never used as identity.

The grouped **All** source list selects nearest upcoming dates first, then latest
past dates. **Upcoming only** selects earliest first; **Past only** selects
latest first. Date boundaries use HA's time zone. This does not change legacy
raw-list sorting, `concert_list`, **Concerts shown** (filtered/capped raw
performances), or **Total concerts** (the API's artist-performance/setlist total).

The native **Unique concert visits** count instead uses all fetched pages,
independent of card settings, integration filters and display caps. It is unknown
if coverage or grouping is incomplete, including ambiguous first-page 404s or
missing IDs; only a confirmed empty history establishes zero. Cards are a view of
the integration's **bounded grouped payload**, not that whole history.

Performances with missing venue identity stay separate and display an
uncertain-grouping warning. Incomplete upstream coverage is also warned about.
To bound state size, the integration includes at most **100 performances per
visit** and **500 overall** in `concert_visits`. Each visit reports
`performance_count` and `omitted_performance_count`; resource overflow produces
an explicit warning, not silent artist truncation. These bounds do not alter the
native visit count. Normal section limits select visits, not a subset of each
included visit's lineup. See the full [attribute contract](README.md#grouped-display-attributes).

If grouping is enabled against an older integration without `concert_visits`,
the card shows a helpful notice that grouping requires an updated integration.
Update/restart Home Assistant and reload the browser, or disable the toggle to
keep using the legacy list. There is **no approximate JavaScript grouping**
fallback, and grouping never makes extra API requests.

## Installation and updates

Tested with **Home Assistant 2025.1.4 and 2026.9.4**, including their actual frontends; see [INSTALL.md](INSTALL.md) and `hacs.json` for the integration's supported minimum. Entity-specific suggestions under **By entity** are optional and available in HA 2026.6 and later. The normal **By cards** workflow does not depend on suggestions.

The integration registers a single bundled JavaScript file through HA's asynchronous static-path API and public frontend module loader. The module waits for HA's own card element in the active browser registry before publishing its card types, avoiding HA's bootstrap registry replacement race. Its content hash changes the resource URL on updates. Restart HA after upgrading and reload open browser/Companion App views to load the new custom-element definitions. Only the JavaScript asset is publicly served, not the integration's source or account data. There are no API credentials in the bundle.

Account reloads and removal do not unregister the shared card types for the running HA instance. Saved cards remain on the dashboard and show a missing/unavailable-account message when appropriate. If you remove every account and restart HA (so the integration no longer loads), or uninstall the integration, its card definitions will no longer be loaded; remove those cards or reinstall/reconfigure the integration.

If cards do not appear, confirm the integration is installed and loaded, restart HA, and reload the browser. Inspect HA logs for frontend setup errors. Do not add a duplicate manual resource as a workaround.

## Optional YAML

The existing `DASHBOARD_COMPLETE.yaml`, `DASHBOARD_COMPACT.yaml`, `DASHBOARD_DELUXE.yaml`, `DASHBOARD_MOBILE.yaml` and [DASHBOARDS.md](DASHBOARDS.md) examples remain optional dashboard-view templates. They are not required by these cards and may include separately installed custom cards. Replace example entity IDs with your actual IDs.

Advanced users can also configure an individual bundled card as YAML:

```yaml
type: custom:setlistfm-complete-card
entity: sensor.alex_concerts
title: My concerts
filter: all
limit: 5
show_location: true
show_songs: true
group_by_visit: false
```

Use `setlistfm-compact-card`, `setlistfm-deluxe-card` or `setlistfm-mobile-card` for the other presets. `filter` accepts `all`, `upcoming` or `past`; `limit` is an integer from 1 to 50. Set `group_by_visit: true` to count section limits in visits and display grouped lineups. Never put your API key in a dashboard.

## Development verification

The runtime bundle needs no build step. Browser-test tooling is development-only:

```text
npm ci
npx playwright install chromium
npm test
```

Playwright runs the real web components in Chromium against a local HA-themed fixture: discovery metadata, visual-editor events and keyboard actions, exact entity selection, dates/time zones, hostile text/URLs, lifecycle, states and responsive light/dark layouts. Layout tests save screenshots in `test-results` (or `PLAYWRIGHT_OUTPUT_DIR`). The fixture is explicitly **not the actual HA card picker**; discovery metadata tests alone do not demonstrate end-to-end picker operation.

Run `python -m pytest` in the supported Linux/Python test environment with `requirements-test.txt` installed. Frontend backend tests cover public module registration, concurrent/repeated setup, retry failures, content-hash cache busting and serving the asset through HA's real HTTP implementation.

### Reproducible real Home Assistant picker smoke

The opt-in `tests/test_live_frontend.py` host and `npm run test:ha` browser driver exercise the **actual HA frontend**, not the themed fixture. Use either `requirements-test.txt` with Python 3.14 (HA 2026.9.4 / frontend 20260826.7) or `requirements-test-min.txt` with Python 3.13 (HA 2025.1.4 / frontend 20250109.2), plus the browser tools above. From the repository root, use two terminals with `SETLISTFM_LIVE_DIR` pointing to the same **new, empty, temporary directory**:

```text
# Terminal 1 (Linux / supported HA Python): set SETLISTFM_LIVE_DIR, then
python -m pytest tests/test_live_frontend.py -q -s

# Terminal 2 (Node/Chromium): set SETLISTFM_LIVE_DIR, then
npm run test:ha
```

On Windows/WSL, Python uses the Linux spelling of that shared directory, and Node uses the Windows spelling. WSL loopback forwarding must be enabled. The Python host waits up to five minutes; the browser waits up to one minute for the host.

The host uses an isolated HA test config, synthetic authentication, an in-memory recorder, and explicit frontend/Lovelace shell components. Two real integration config entries load fictional accounts from the [local mock API](devtools/setlistfm_mock/README.md) over actual loopback HTTP; the real client, coordinator, native entities and entity registry are exercised before renaming their concerts sensors. The API endpoint patch exists only in the fixture. The server journal verifies two pages for one account and an empty second account, with dummy-key validation.

One invalid API record is removed by the integration before publishing its sensor attributes. The browser verifies the incompleteness notice using these real sanitized attributes, while still displaying the valid concerts.

No `default_config`, discovery scanning, real account or live API key is used. Backend sockets are restricted to loopback, HA's HTTP listener is explicitly loopback-only, and unrelated brand artwork/built-in card preview images are served as local placeholders. Screenshots and `live-result.json` are saved in the supplied directory. The temporary `live-host.json` contains synthetic local auth and is removed on normal teardown; remove it if you interrupt the host.

The smoke verifies all four visible presets (Community on current HA, Custom cards on minimum HA), the real editor's account selector excluding the other native sensors, empty previews, title/filter/limit/song options, saving the card, rendering after reload, and absence of browser errors. Python additionally checks saved Lovelace storage and real API requests. The host is skipped in the normal suite; enable it explicitly for either supported test environment.

The **Frontend** GitHub Actions workflow runs the browser fixture suite and this full mock-API-to-card smoke on both HA versions, retaining screenshots and the credential-free result summary as artifacts.

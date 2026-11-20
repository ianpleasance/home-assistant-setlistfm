# Quick Start Installation Guide

## Prerequisites

- Home Assistant 2025.1.0 or newer (typed runtime data and explicit coordinator entry)
- Setlist.fm account
- Setlist.fm API key ([get one here](https://www.setlist.fm/settings/api))

## Installation Steps

### 1. Install the Integration

**Option A: Manual Installation**
```bash
# Copy the setlistfm folder to your custom_components directory
cd /config
mkdir -p custom_components
cp -r /path/to/home-assistant-setlistfm/custom_components/setlistfm custom_components/
```

**Option B: HACS Installation**

HACS must already be installed. Open the upstream repository using this button,
then confirm installation in HACS. My Home Assistant asks for your instance URL
the first time; this is not an unattended installer.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ianpleasance&repository=home-assistant-setlistfm&category=integration)

If the link does not work, use the manual
[custom repository steps](https://www.hacs.xyz/docs/faq/custom_repositories/):

1. Open HACS
2. Go to Integrations
3. Click ⋮ → Custom repositories
4. Add: `https://github.com/ianpleasance/home-assistant-setlistfm`
5. Category: Integration
6. Install "Setlist.fm"

For testing a fork, use its own GitHub URL in these custom repository steps
instead. The badge deliberately retains the upstream project identity.

### 2. Restart Home Assistant
```bash
# Restart Home Assistant to load the integration
```

### 3. Get Your Credentials

**Username**:
1. Go to your Setlist.fm profile
2. Look at the URL: `https://www.setlist.fm/user/YOUR_USERNAME`
3. Copy only `YOUR_USERNAME`, not the full URL or your display name. It is also shown at the top right next to **Add setlist**
4. Capitalization and surrounding spaces are handled automatically: `Blabla` becomes `blabla`

**API Key**:
1. Visit https://www.setlist.fm/settings/api
2. Request an API key and wait for approval if needed
3. Copy your API key

### 4. Add the Integration

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Setlist.fm**
4. Fill in the form:
   - **Username**: Your Setlist.fm profile username
   - **API Key**: Your API key
   - **Name** (optional): A friendly name (e.g., "John")
5. Click **Submit**

### 5. Configure Options (Optional)

1. In Devices & Services, find your Setlist.fm integration
2. Click **Configure**
3. Adjust settings:
   - **Refresh Period**: 1-24 hours (default: 6)
   - **Number of Concerts**: 1-50 (default: 10); maximum individual performances in the legacy list and, independently, maximum visits in the grouped list
   - **Date Format**: DD-MM-YYYY, MM-DD-YYYY, etc.
   - **Show Concerts**: All / Upcoming only / Past only

### 6. Verify It's Working

Open the user's service device and check the five sensors **Concerts shown**, **Total
concerts**, **Unique concert visits**, **Next concert** and diagnostic **Last successful update**, plus the
**Refresh** button under configuration controls. The device links to the user's
setlist.fm profile. Unknown totals/dates are not zero; unavailable sensors mean
the latest retrieval failed. The button can retry a failed connection.
**Concerts shown** is the filtered, display-limited count, not lifetime attendance;
for example, it can show 10 while **Total concerts** shows 45. Its previous default
name was **Concerts**; existing entity IDs and custom names are preserved.

**Total concerts** counts API artist performances/setlists, not visits.
**Unique concert visits** counts distinct dates and venue IDs across all fetched
pages, independent of display filters and limits. Three artists at one venue on
one date count as one visit. Independent shows on the same venue-day also merge;
festival stages with different venue IDs do not. Names are not used to guess
venue identity. A confirmed empty history gives zero; incomplete data, an ambiguous
404, invalid dates or missing venue identity give unknown. All five sensors share
the same refresh; the new count adds no API requests.

## First Use

### View Your Concerts Without YAML

1. Edit a dashboard and choose **Add card > By card** (or **By cards**).
2. Find the **Community** section or search for `setlist.fm`. On HA 2025.1,
   the picker calls these **Custom: setlist.fm** cards instead.
3. Choose **Complete**, **Compact**, **Deluxe** or **Mobile**.
4. Select the account's **Concerts shown** entity (or its custom name), adjust the visual options and save.
5. Optionally enable **Group by concert visit** (off by default) in any preset to
   show venue-day lineups with artists in alphabetical order, individual setlist
   links and song counts.

The cards are bundled and automatically loaded; no separate frontend repository,
manual JavaScript resource, or YAML copying is needed. These are individual cards,
not whole dashboard views. See [CARDS.md](CARDS.md) for examples and limitations.
After an upgrade, restart HA and reload your browser/Companion App view.

Grouped cards use the integration's separately filtered and capped
`concert_visits` list, not the native visit-count sensor or the whole history.
The card's section limit counts visits when grouping is on and performances
otherwise. Missing venue identities are shown separately with a warning, never
merged by name. Resource bounds (100 performances per visit, 500 overall) show
explicit omissions without changing the native count. If grouping reports that an
updated integration is required, update/restart the integration and reload the
browser; the card does not guess groups from an older sensor.

The earlier YAML dashboards remain an optional alternative:

```yaml
type: markdown
title: My Concerts
content: |
  {{ state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') }}
```

Replace each **entire entity ID** in examples with the ID in your entity settings.
HA generates IDs from names and translations; there is no guaranteed `setlistfm_`
prefix. Existing Concerts IDs and custom names are preserved on upgrade.
Alternatively, use **Edit dashboard → Add card → Entities** and select the entities
visually, without YAML.

### Check Status

Add an entities card:

```yaml
type: entities
title: Setlist.fm Status
entities:
  - sensor.setlistfm_yourname_concerts
  - sensor.yourname_total_concerts
  - sensor.yourname_unique_concert_visits
  - sensor.yourname_next_concert
  - sensor.setlistfm_yourname_last_update
  - button.yourname_refresh
```

## Troubleshooting

### Integration Not Showing Up
- Verify files are in `/config/custom_components/setlistfm/`
- Check logs: Settings → System → Logs
- Restart Home Assistant again

### "Invalid API Key" Error
- Verify your API key is correct (copy/paste carefully)
- Check your API key is approved on Setlist.fm
- Make sure there are no extra spaces
- Use Home Assistant's reauthentication prompt to replace a rejected key. It
  preserves this account and its existing entities; do not delete/re-add it.

### Refresh and Removal

Press the device's **Refresh** button or use **Developer Tools → Actions →
setlistfm.refresh**, selecting a loaded entry. Leaving the entry field omitted
refreshes all loaded accounts; an invalid explicit target is an error. These
controls wait for the actual result and respect API cooldowns.

Delete an account from its integration entry menu to stop polling and remove its
HA entities. No setlist.fm data is deleted. See [reauthentication and
removal](README.md#reauthentication-and-removal).

### Empty Attendance or an Unknown Total
- Verify your username is correct (capitalization is handled automatically).
- Use only the username from `setlist.fm/user/YOUR_USERNAME`.
- Setup checks the attended endpoint, not account existence. A first-page 404 is
  ambiguous: setup accepts it, but the total remains unknown and coverage incomplete.
  A metadata-confirmed empty account has total zero and complete coverage.
- See [API behavior and coverage](README.md#api-behavior-and-coverage) for limitations.

### Unknown Unique Concert Visits
- Check `grouping_complete`, `identified_visit_count`,
  `unidentified_performance_count` and `invalid_date_count` on **Concerts shown**.
- Missing venue IDs and incomplete attendance cannot establish a unique total.
  An identified partial count is not proof of a complete history.
- Date filters and display limits do not change the native visit count. There is
  no separate upcoming API: only future-dated setlists returned by the attended
  endpoint can appear.

### No Concerts Showing
- Check you have concerts logged on Setlist.fm
- Check the filter settings (All/Upcoming/Past)
- Check `total_attended`, `fetched_count`, `complete`, and `completeness_reason`
  to distinguish display filtering from unknown or incomplete attendance.

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.setlistfm: debug
```

Then restart and check: Settings → System → Logs

## Next Steps

- [Read the full README](README.md) for detailed features
- [Check usage examples](README.md#usage-examples)
- [Set up automations](README.md#automation-example)
- [Report an issue](https://github.com/ianpleasance/home-assistant-setlistfm/issues)

## Getting Help

1. Check [Troubleshooting](README.md#troubleshooting)
2. Search [existing issues](https://github.com/ianpleasance/home-assistant-setlistfm/issues)
3. Enable debug logging and check logs
4. [Open a new issue](https://github.com/ianpleasance/home-assistant-setlistfm/issues/new) with:
   - Home Assistant version
   - Integration version
   - Relevant logs (with API key redacted!)
   - Steps to reproduce

## Multiple Users

To add multiple Setlist.fm accounts:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration** again
3. Search for **Setlist.fm**
4. Add the second user's credentials
5. Repeat for each user

Each user gets their own sensors and can have different settings!

## Migrating from v1.x?

See [Migration from v1.x](README.md#migration-from-v1x) for the old YAML-based version.

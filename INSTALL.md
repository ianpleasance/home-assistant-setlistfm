# Quick Start Installation Guide

## Prerequisites

- Home Assistant 2024.1.0 or newer
- Setlist.fm account
- Setlist.fm API key ([get one here](https://www.setlist.fm/settings/api))

## Installation Steps

### 1. Install the Integration

**Option A: Manual Installation**
```bash
# Copy the setlistfm folder to your custom_components directory
cd /config
mkdir -p custom_components
cp -r setlistfm custom_components/
```

**Option B: HACS Installation**
1. Open HACS
2. Go to Integrations
3. Click ⋮ → Custom repositories
4. Add: `https://github.com/ianpleasance/home-assistant-setlistfm`
5. Category: Integration
6. Install "Setlist.fm"

### 2. Restart Home Assistant
```bash
# Restart Home Assistant to load the integration
```

### 3. Get Your Credentials

**User ID**:
1. Go to your Setlist.fm profile
2. Look at the URL: `https://www.setlist.fm/user/YOUR_USER_ID`
3. Copy `YOUR_USER_ID`

**API Key**:
1. Visit https://www.setlist.fm/settings/api
2. Request an API key (instant approval for personal use)
3. Copy your API key

### 4. Add the Integration

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Setlist.fm**
4. Fill in the form:
   - **User ID**: Your Setlist.fm user ID
   - **API Key**: Your API key
   - **Name** (optional): A friendly name (e.g., "John")
5. Click **Submit**

### 5. Configure Options (Optional)

1. In Devices & Services, find your Setlist.fm integration
2. Click **Configure**
3. Adjust settings:
   - **Refresh Period**: 1-24 hours (default: 6)
   - **Number of Concerts**: 1-50 (default: 10)
   - **Date Format**: DD-MM-YYYY, MM-DD-YYYY, etc.
   - **Show Concerts**: All / Upcoming only / Past only

### 6. Verify It's Working

Check that entities were created:
- `sensor.setlistfm_{name}_concerts` - Your concert list
- `sensor.setlistfm_{name}_last_update` - Last update time

## First Use

### View Your Concerts

Add a card to your dashboard:

```yaml
type: markdown
title: My Concerts
content: |
  {{ state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') }}
```

Replace `yourname` with the name you configured.

### Check Status

Add an entities card:

```yaml
type: entities
title: Setlist.fm Status
entities:
  - sensor.setlistfm_yourname_concerts
  - sensor.setlistfm_yourname_last_update
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

### "User Not Found" Error
- Verify your User ID is correct
- Check the URL format: `setlist.fm/user/YOUR_ID`
- Ensure your profile is public

### No Concerts Showing
- Check you have concerts logged on Setlist.fm
- Check the filter settings (All/Upcoming/Past)
- Look at `total_attended` attribute to verify data is fetched

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
- [Join discussions](https://github.com/ianpleasance/home-assistant-setlistfm/discussions)

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

See [MIGRATION.md](MIGRATION.md) for detailed migration instructions from the old YAML-based version.

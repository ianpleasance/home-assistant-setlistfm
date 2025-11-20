# Setlist.fm Integration for Home Assistant

This custom integration allows you to display your concert attendance data from [Setlist.fm](https://www.setlist.fm) in Home Assistant.

## Features

- ✅ **UI Configuration** - No YAML required! Configure through the Home Assistant UI
- ✅ **Async/Await** - Non-blocking API calls that won't freeze your Home Assistant
- ✅ **Multiple Users** - Add multiple Setlist.fm accounts
- ✅ **Flexible Filtering** - Show past concerts, upcoming concerts, or all
- ✅ **Customizable Display** - Choose date format and number of concerts to display
- ✅ **Automatic Updates** - Configurable refresh interval (1-24 hours)
- ✅ **Rate Limiting Protection** - Built-in retry logic for API rate limits
- ✅ **Proper Entity Registry** - Entities have unique IDs for proper HA integration

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right and select "Custom repositories"
4. Add `https://github.com/ianpleasance/home-assistant-setlistfm` as an integration repository
5. Click "Install" on the Setlist.fm card
6. Restart Home Assistant

### Manual Installation

1. Copy the `setlistfm` folder to your `custom_components` directory
2. Restart Home Assistant

## Configuration

### Getting Your Setlist.fm Credentials

1. **User ID**: 
   - Go to your Setlist.fm profile
   - Your User ID is in the URL: `https://www.setlist.fm/user/YOUR_USER_ID`

2. **API Key**:
   - Go to https://www.setlist.fm/settings/api
   - Request an API key (it's free!)
   - Copy the API key once approved

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Setlist.fm"
4. Enter your User ID and API Key
5. (Optional) Enter a friendly name
6. Click **Submit**

### Configuring Options

After adding the integration, you can configure options:

1. Go to **Settings** → **Devices & Services**
2. Find your Setlist.fm integration
3. Click **Configure**
4. Adjust the following options:
   - **Refresh Period**: How often to check for updates (1-24 hours, default: 6)
   - **Number of Concerts**: How many concerts to display (1-50, default: 10)
   - **Date Format**: Choose your preferred date format
     - `DD-MM-YYYY` (31-12-2024)
     - `DD-MM-YY` (31-12-24)
     - `MM-DD-YYYY` (12-31-2024)
     - `MM-DD-YY` (12-31-24)
   - **Show Concerts**: Filter which concerts to display
     - `All concerts` - Show both past and upcoming
     - `Upcoming only` - Only show future concerts
     - `Past only` - Only show attended concerts

## Entities Created

For each configured user, the integration creates two sensors:

### 1. Concerts Sensor
**Entity ID**: `sensor.setlistfm_{name}_concerts`

**State**: Number of concerts (based on your filters)

**Attributes**:
```json
{
  "concerts": [
    {
      "id": "134f893d",
      "date": "05-11-2025",
      "artist": {
        "name": "Black Bordello",
        "mbid": "75fd16ad-3c6b-4357-af72-71a344bacb4c"
      },
      "venue": {
        "name": "Hot Box",
        "city": "Chelmsford",
        "state": "England",
        "country": "United Kingdom"
      },
      "song_count": 9,
      "url": "https://www.setlist.fm/setlist/..."
    }
  ],
  "concert_list": "Artist at Venue in City on DD-MM-YYYY\n...",
  "total_attended": 150
}
```

- `concerts`: Simplified JSON array of concert data
- `concert_list`: Formatted text list (one concert per line)
- `total_attended`: Total concerts attended from user profile (all time)

**Example**:
```
State: 10
Attributes:
  concerts: [
    {
      "id": "abc123",
      "date": "31-12-2024",
      "artist": {
        "name": "The Beatles",
        "mbid": "..."
      },
      "venue": {
        "name": "Royal Albert Hall",
        "city": "London",
        "state": "England",
        "country": "United Kingdom"
      },
      "song_count": 15,
      "url": "https://www.setlist.fm/setlist/..."
    }
  ]
  concert_list: |
    The Beatles at Royal Albert Hall in London on 31-12-2024
    Pink Floyd at Madison Square Garden in New York on 15-11-2024 (Upcoming)
    Queen at Wembley Stadium in London on 12-07-2024
  total_attended: 150
```

### 2. Last Update Sensor
**Entity ID**: `sensor.setlistfm_{name}_last_update`

**State**: Timestamp of last successful update

**Attributes**:
- `last_update_success`: Boolean indicating if last update was successful
- `last_error`: Error message (if any)

## Services

### `setlistfm.force_refresh_{entry_id}`

Force an immediate refresh of concert data for a specific user.

**Example Automation**:
```yaml
automation:
  - alias: "Refresh Setlist.fm Daily"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: setlistfm.force_refresh_abc123def456
```

## Usage Examples

### 🎨 Beautiful Dashboards

Want to create stunning concert dashboards with emojis and visual flair? Check out our comprehensive **[DASHBOARDS.md](DASHBOARDS.md)** guide with:

- 🎸 Complete dashboard layouts
- 🎤 Individual card examples  
- 📊 Stats cards with emojis
- 🎯 Next concert countdowns
- 🗓️ Calendar views
- 🌈 Mushroom card examples
- 🎨 Custom styling options

### Display in Lovelace

**Simple Markdown Card**:
```yaml
type: markdown
content: |
  ## 🎵 My Concerts
  {{ state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') }}
```

**Entities Card**:
```yaml
type: entities
entities:
  - sensor.setlistfm_yourname_concerts
  - sensor.setlistfm_yourname_last_update
```

**Quick Upcoming Concerts**:
```yaml
type: markdown
title: 🎤 Upcoming Shows
content: |
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
  {% set upcoming = concerts.split('\n') | select('search', 'Upcoming') | list %}
  {% for concert in upcoming %}
  🔜 {{ concert.replace('(Upcoming)', '') }}
  {% endfor %}
```

### Automation Example

Send a notification when you have an upcoming concert:

```yaml
automation:
  - alias: "Upcoming Concert Reminder"
    trigger:
      - platform: state
        entity_id: sensor.setlistfm_yourname_concerts
    condition:
      - condition: template
        value_template: >
          {{ 'Upcoming' in state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') }}
    action:
      - service: notify.mobile_app
        data:
          title: "Concert Reminder"
          message: >
            You have upcoming concerts!
            {{ state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') }}
```

## Migration from v1.x

If you were using the old YAML-based version:

1. **Backup your configuration** - Copy your YAML config before removing it
2. **Install the new version** - Follow installation steps above
3. **Remove YAML configuration** - Delete the `setlistfm:` section from `configuration.yaml`
4. **Add via UI** - Configure through the UI as described above
5. **Update automations** - Entity IDs have changed:
   - Old: `text.setlistfm_{name}_concerts` → New: `sensor.setlistfm_{name}_concerts`
   - Attribute changed: Access via `state_attr('sensor.setlistfm_{name}_concerts', 'concert_list')`

### Entity ID Changes

| Old Entity | New Entity |
|------------|------------|
| `text.setlistfm_{name}_concerts` | `sensor.setlistfm_{name}_concerts` |
| `sensor.setlistfm_{name}_last_update` | `sensor.setlistfm_{name}_last_update` (unchanged) |
| `sensor.setlistfm_{name}_response` | Removed (now in attributes) |

## Troubleshooting

### "Invalid API Key" Error
- Verify your API key is correct
- Check if your API key has been approved by Setlist.fm
- Request a new API key if needed

### "User Not Found" Error
- Verify your User ID is correct
- Check your Setlist.fm profile is public

### No Concerts Showing
- Check your filter settings (upcoming/past/all)
- Verify you have concerts logged on Setlist.fm
- Check the `total_attended` attribute to see if data is being fetched

### Rate Limiting
- The integration has built-in retry logic
- Default refresh is 6 hours to avoid rate limits
- Consider increasing the refresh period if you hit rate limits

## API Rate Limits

Setlist.fm has rate limits on their API:
- **Recommendation**: Use refresh periods of 6+ hours
- The integration automatically retries (3 attempts) when rate limited
- Check the `last_update` sensor for error messages

## Support

- **Issues**: [GitHub Issues](https://github.com/ianpleasance/home-assistant-setlistfm/issues)
- **Documentation**: [GitHub README](https://github.com/ianpleasance/home-assistant-setlistfm)

## Credits

- Original version by [@ianpleasance](https://github.com/ianpleasance)
- Modernized for Home Assistant 2024+ with config flow support

## License

This project is licensed under the Apache 2.0.

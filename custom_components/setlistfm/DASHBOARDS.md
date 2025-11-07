# 🎸 Beautiful Dashboard Examples

Here are several dashboard card examples to display your Setlist.fm concerts in style!

## 🎨 Complete Dashboard Layout

### Full Concert Dashboard (Recommended)

```yaml
title: 🎵 My Concerts
path: concerts
cards:
  # Header Card
  - type: markdown
    content: |
      # 🎸 Concert Tracker
      Track all your attended and upcoming concerts from Setlist.fm
    
  # Stats Row
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-template-card
        primary: "{{ states('sensor.setlistfm_yourname_concerts') }}"
        secondary: Concerts Shown
        icon: mdi:music-note-multiple
        icon_color: purple
        tap_action:
          action: none
      
      - type: custom:mushroom-template-card
        primary: "{{ state_attr('sensor.setlistfm_yourname_concerts', 'total_attended') }}"
        secondary: Total Attended
        icon: mdi:ticket
        icon_color: amber
        tap_action:
          action: none
      
      - type: custom:mushroom-template-card
        primary: "{{ relative_time(states('sensor.setlistfm_yourname_last_update')) }}"
        secondary: Last Updated
        icon: mdi:clock-outline
        icon_color: blue
        tap_action:
          action: call-service
          service: setlistfm.force_refresh_YOUR_ENTRY_ID
  
  # Upcoming Concerts Section
  - type: markdown
    content: |
      ## 🎤 Upcoming Concerts
      
      {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
      {% if concerts %}
        {% set lines = concerts.split('\n') %}
        {% set upcoming = lines | select('search', 'Upcoming') | list %}
        {% if upcoming | length > 0 %}
          {% for concert in upcoming %}
      🎵 {{ concert.replace('(Upcoming)', '🔜') }}
          {% endfor %}
        {% else %}
      😔 No upcoming concerts scheduled
        {% endif %}
      {% else %}
      💤 No concert data available
      {% endif %}
  
  # Recent/Past Concerts Section
  - type: markdown
    content: |
      ## 🎸 Recent Concerts
      
      {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
      {% if concerts %}
        {% set lines = concerts.split('\n') %}
        {% set past = lines | reject('search', 'Upcoming') | list %}
        {% if past | length > 0 %}
          {% for concert in past[:5] %}
      ✅ {{ concert }}
          {% endfor %}
        {% else %}
      😔 No past concerts recorded
        {% endif %}
      {% else %}
      💤 No concert data available
      {% endif %}
  
  # Concert Timeline (All)
  - type: markdown
    content: |
      ## 📅 Full Concert Timeline
      
      {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
      {% if concerts %}
        {% set lines = concerts.split('\n') %}
        {% for concert in lines %}
          {% if 'Upcoming' in concert %}
      🔜 {{ concert.replace('(Upcoming)', '') }}
          {% else %}
      🎵 {{ concert }}
          {% endif %}
        {% endfor %}
      {% else %}
      💤 No concerts to display
      {% endif %}
```

---

## 🎯 Individual Card Examples

### 1. 🎤 Upcoming Concerts Card (Emoji-Rich)

```yaml
type: markdown
title: 🎤 Upcoming Shows
content: |
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
  {% if concerts %}
    {% set lines = concerts.split('\n') %}
    {% set upcoming = lines | select('search', 'Upcoming') | list %}
    {% if upcoming | length > 0 %}
      {% for concert in upcoming %}
  🎸 {{ concert.replace('(Upcoming)', '🔜') }}
      {% endfor %}
      
  ---
  🎫 **{{ upcoming | length }}** upcoming concert{{ 's' if upcoming | length != 1 else '' }}
    {% else %}
  😔 No upcoming concerts
  
  💡 Log your next show on [Setlist.fm](https://www.setlist.fm)
    {% endif %}
  {% else %}
  ⏳ Loading concert data...
  {% endif %}
```

### 2. 🎸 Recent Concerts Card (Last 5)

```yaml
type: markdown
title: 🎸 Recently Attended
content: |
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
  {% if concerts %}
    {% set lines = concerts.split('\n') %}
    {% set past = lines | reject('search', 'Upcoming') | list %}
    {% if past | length > 0 %}
      {% for concert in past[:5] %}
  ✨ {{ concert }}
      {% endfor %}
      
  ---
  🎭 **{{ state_attr('sensor.setlistfm_yourname_concerts', 'total_attended') }}** total concerts attended!
    {% else %}
  🎵 No past concerts yet
  
  💡 Start logging your concerts on [Setlist.fm](https://www.setlist.fm)
    {% endif %}
  {% else %}
  ⏳ Loading concert data...
  {% endif %}
```

### 3. 📊 Stats Card (Overview)

```yaml
type: entities
title: 📊 Concert Statistics
entities:
  - entity: sensor.setlistfm_yourname_concerts
    name: Concerts Shown
    icon: mdi:music-note-multiple
  - type: attribute
    entity: sensor.setlistfm_yourname_concerts
    attribute: total_attended
    name: Total Attended
    icon: mdi:ticket-confirmation
  - entity: sensor.setlistfm_yourname_last_update
    name: Last Updated
    icon: mdi:update
```

### 4. 🎯 Next Concert Countdown

```yaml
type: markdown
title: 🎯 Next Concert
content: |
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
  {% if concerts %}
    {% set lines = concerts.split('\n') %}
    {% set upcoming = lines | select('search', 'Upcoming') | list %}
    {% if upcoming | length > 0 %}
  
  ## 🎤 {{ upcoming[0].split(' at ')[0] }}
  
  📍 **{{ upcoming[0].split(' at ')[1].split(' on ')[0] }}**
  
  📅 **{{ upcoming[0].split(' on ')[1].replace('(Upcoming)', '').strip() }}**
  
  🎫 Get excited! Your next show is coming up!
    {% else %}
  
  😔 **No upcoming concerts**
  
  🔍 Time to find your next show!
  
  💡 [Browse concerts on Setlist.fm](https://www.setlist.fm)
    {% endif %}
  {% else %}
  ⏳ Loading...
  {% endif %}
```

### 6. 🎵 Concert Details with Song Counts

```yaml
type: markdown
title: 🎵 Concert Details
content: |
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concerts') %}
  {% if concerts %}
    {% for concert in concerts[:10] %}
  
  ### 🎤 {{ concert.artist.name }}
  📍 **{{ concert.venue.name }}** - {{ concert.venue.city }}, {{ concert.venue.country }}
  📅 **{{ concert.date }}**
  🎵 **{{ concert.song_count }}** songs performed
  🔗 [View Setlist]({{ concert.url }})
  
    {% endfor %}
  {% else %}
  ⏳ No concert data
  {% endif %}
```

### 7. 🗓️ Calendar View (Month by Month)

```yaml
type: markdown
title: 🗓️ Concert Calendar
content: |
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concerts') %}
  {% if concerts %}
    {% set ns = namespace(current_month='') %}
    {% for concert in concerts[:20] %}
      {% set date = concert.eventDate %}
      {% set month = date.split('-')[1] + '/' + date.split('-')[2] %}
      {% if month != ns.current_month %}
        {% set ns.current_month = month %}
  
  ### 📅 {{ ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month.split('/')[0]|int - 1] }} {{ month.split('/')[1] }}
      {% endif %}
  🎵 **{{ concert.artist.name }}** at {{ concert.venue.name }}
    {% endfor %}
  {% else %}
  ⏳ No concerts available
  {% endif %}
```

---

## 🎨 Mushroom Card Examples (Requires Mushroom Cards)

### Install Mushroom Cards First
```
HACS → Frontend → Search "Mushroom" → Install
```

### Concert Stats with Mushroom

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-title-card
    title: 🎸 My Concert Journey
    
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.setlistfm_yourname_concerts
        name: Shown
        icon: mdi:music-note-multiple
        icon_color: purple
        
      - type: custom:mushroom-template-card
        primary: "{{ state_attr('sensor.setlistfm_yourname_concerts', 'total_attended') }}"
        secondary: Total
        icon: mdi:ticket
        icon_color: amber
        
  - type: custom:mushroom-entity-card
    entity: sensor.setlistfm_yourname_last_update
    name: Last Update
    icon: mdi:clock-outline
    icon_color: blue
    tap_action:
      action: call-service
      service: setlistfm.force_refresh_YOUR_ENTRY_ID
```

### Next Concert - Mushroom Style

```yaml
type: custom:mushroom-template-card
primary: |
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
  {% if concerts %}
    {% set upcoming = concerts.split('\n') | select('search', 'Upcoming') | list %}
    {% if upcoming | length > 0 %}
      {{ upcoming[0].split(' at ')[0] }}
    {% else %}
      No upcoming concerts
    {% endif %}
  {% else %}
    Loading...
  {% endif %}
secondary: |
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
  {% if concerts %}
    {% set upcoming = concerts.split('\n') | select('search', 'Upcoming') | list %}
    {% if upcoming | length > 0 %}
      {{ upcoming[0].split(' on ')[1].replace('(Upcoming)', '').strip() }}
    {% else %}
      Find your next show!
    {% endif %}
  {% else %}
    ...
  {% endif %}
icon: mdi:ticket
icon_color: >
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
  {% if concerts %}
    {% set upcoming = concerts.split('\n') | select('search', 'Upcoming') | list %}
    {{ 'green' if upcoming | length > 0 else 'grey' }}
  {% else %}
    grey
  {% endif %}
badge_icon: mdi:calendar-clock
badge_color: purple
tap_action:
  action: url
  url_path: https://www.setlist.fm
```

---

## 🌈 Enhanced Markdown Card (Beautiful Timeline)

```yaml
type: markdown
title: 🎭 Concert Timeline
content: |
  <style>
    .concert-upcoming { color: #4CAF50; font-weight: bold; }
    .concert-past { color: #9E9E9E; }
    .concert-header { font-size: 1.2em; margin-top: 15px; }
  </style>
  
  {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
  {% if concerts %}
    {% set lines = concerts.split('\n') %}
    
    {% set upcoming = lines | select('search', 'Upcoming') | list %}
    {% if upcoming | length > 0 %}
  <div class="concert-header">🔜 Upcoming Concerts ({{ upcoming | length }})</div>
      {% for concert in upcoming %}
  <div class="concert-upcoming">🎤 {{ concert.replace('(Upcoming)', '') }}</div>
      {% endfor %}
    {% endif %}
    
    {% set past = lines | reject('search', 'Upcoming') | list %}
    {% if past | length > 0 %}
  <div class="concert-header">✅ Recent Concerts</div>
      {% for concert in past[:5] %}
  <div class="concert-past">🎸 {{ concert }}</div>
      {% endfor %}
    {% endif %}
    
  ---
  **Total Concerts:** {{ state_attr('sensor.setlistfm_yourname_concerts', 'total_attended') }} 🎫
  **Last Updated:** {{ relative_time(states('sensor.setlistfm_yourname_last_update')) }} ⏰
  {% else %}
  ⏳ Loading concert data...
  {% endif %}
```

---

## 🎪 Fun Emoji Options

Use these emoji combinations for different vibes:

### Rock/Metal Concerts
```
🤘 🎸 🥁 🎤 ⚡ 🔥 💀 🎭
```

### Pop/Mainstream
```
🎤 🎵 🎶 ✨ 💫 ⭐ 🌟 🎪
```

### Electronic/DJ
```
🎧 🎚️ 🎛️ 💿 🔊 🌈 ⚡ 🌙
```

### Classical/Jazz
```
🎻 🎺 🎷 🎹 🥁 🎼 🎶 🎵
```

### Festival Vibes
```
🎪 🎡 🎢 🎠 🎨 🌈 ⛺ 🎉
```

---

## 🎯 Emoji Status Indicators

Use these in your templates:

```yaml
# Upcoming concert: 🔜 ⏰ 📅 🎫
# Past concert: ✅ ✔️ 🎵 🎸
# Today: 🔥 ⚡ 🎉 🎊
# This week: ⭐ 🌟 💫
# Loading: ⏳ 🔄 ⏱️
# Error: ⚠️ ❌ 🚫
# Empty: 😔 💤 🤷 📭
```

---

## 🎨 Complete Example Dashboard (Copy-Paste Ready)

```yaml
title: My Concerts
path: setlistfm
icon: mdi:music
cards:
  # Header
  - type: markdown
    content: |
      # 🎸 My Concert Tracker
      Your musical journey on Setlist.fm
  
  # Quick Stats
  - type: horizontal-stack
    cards:
      - type: entity
        entity: sensor.setlistfm_yourname_concerts
        name: 🎵 Displayed
        icon: mdi:music-note-multiple
      
      - type: markdown
        content: |
          ## 🎫 {{ state_attr('sensor.setlistfm_yourname_concerts', 'total_attended') }}
          **Total Attended**
  
  # Upcoming Section
  - type: markdown
    content: |
      ## 🎤 Coming Up
      
      {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
      {% if concerts %}
        {% set upcoming = concerts.split('\n') | select('search', 'Upcoming') | list %}
        {% if upcoming | length > 0 %}
          {% for concert in upcoming %}
      🔜 {{ concert.replace('(Upcoming)', '') }}
          {% endfor %}
        {% else %}
      😔 No upcoming concerts
      
      💡 [Find concerts near you](https://www.setlist.fm)
        {% endif %}
      {% else %}
      ⏳ Loading...
      {% endif %}
  
  # Recent Section
  - type: markdown
    content: |
      ## 🎸 Recently Attended
      
      {% set concerts = state_attr('sensor.setlistfm_yourname_concerts', 'concert_list') %}
      {% if concerts %}
        {% set past = concerts.split('\n') | reject('search', 'Upcoming') | list %}
        {% if past | length > 0 %}
          {% for concert in past[:5] %}
      ✨ {{ concert }}
          {% endfor %}
        {% else %}
      🎵 No past concerts yet
        {% endif %}
      {% else %}
      ⏳ Loading...
      {% endif %}
  
  # Footer
  - type: entities
    entities:
      - entity: sensor.setlistfm_yourname_last_update
        name: ⏰ Last Updated
        icon: mdi:clock-outline
```

---

## 💡 Pro Tips

### Replace Placeholders
- `yourname` → Your configured name (lowercase)
- `YOUR_ENTRY_ID` → Find in Developer Tools → Services

### Test Templates
Use Developer Tools → Template to test before adding to dashboard

### Customize Emojis
Mix and match emojis based on your music taste and vibe!

### Performance
- Limit to 10-20 concerts max for best performance
- Use `[:5]` or `[:10]` to limit results

---

## 🎨 Color Themes

Add custom colors with CSS in markdown cards:

```yaml
type: markdown
content: |
  <style>
    .upcoming { color: #4CAF50; }
    .past { color: #2196F3; }
    .venue { color: #FF9800; }
  </style>
  
  <span class="upcoming">🎤 Upcoming Concert</span>
  <span class="past">🎸 Past Concert</span>
  <span class="venue">📍 Venue Name</span>
```

---

**Remember**: Replace `yourname` with your actual configured name, and enjoy your beautiful concert dashboard! 🎉

# Home Assistant setlist.fm Integration

This is a custom integration for [Home Assistant](https://www.home-assistant.io/) that allows you to display concerts from [setlist.fm](https://setlist.fm/) for specific users.

## API access

For each user that you want to use this integration for, you will need a setlist.fm API key. When logged into setlist.fm as that user, select the menu dropdown and the "API" option and then request an API key.

## Installation
Copy the setlistfm directory to your Home Assistant custom_components directory:

```sh
cp -r home-assistant-setlistfm/custom_components/setlistfm <your_home_assistant_config_dir>/custom_components/
```
Ensure the setlistfm directory and its contents have the correct permissions:

```sh
chmod -R 755 <your_home_assistant_config_dir>/custom_components/setlistfm
```
## Configuration
Add the following configuration to your `configuration.yaml` file:

```yaml
setlistfm:
  users:
    - userid: "user1"
      name: "User 1"
      api_key: "YOUR_API_KEY"
      refresh_period: 6
      number_of_concerts: 10
      date_format: "%d-%m-%Y"
      show_concerts: "upcoming"  # or "past", or "all"
    - userid: "user2"
      name: "User 2"
      api_key: "YOUR_API_KEY"
      refresh_period: 12
      number_of_concerts: 5
      date_format: "%d-%m-%Y"
      show_concerts: "all"
```
### Parameter Description
| Parameter       | Description |
|----------------|-------------|
| `userid`       | The setlist.fm user ID. |
| `name`         | A friendly name for the user. Used to allow retrieval of and differentiation of multiple users' setlist.fm data |
| `api_key`      | The user's setlist.fm API key. |
| `refresh_period` | The period (in hours) to refresh the data. Defaults to 6. |
| `number_of_concerts` | The number of concerts to display (1-20). Defaults to 10. |
| `date_format`  | The format for displaying dates (`%d-%m-%Y`, `%d-%m-%y`, `%m-%d-%Y`, `%m-%d-%y`). |
| `show_concerts` | Which concerts to show: `upcoming` for upcoming concerts, `past` for past concerts, `all` for both. |

Restart Home Assistant to apply the changes.

The integration creates these entities

| Entity | Description | 
|--------|-------------|
| sensor.setlistfm_(name)_last_update | The date and time of the last update of this user's setlist.fm data |
| sensor.setlistfm_(name)_response | The HTTP response from the last update, if not a 200 then this also contains the error message from the API |
| text.setlistfm_(name)_concerts | A text entity containg the list of concerts for the user | 


## Displaying Concerts in Lovelace
To display the concerts in a Lovelace card, you can use either the **Entities Card** or the **Markdown Card**.

### Entities Card
Open the Lovelace UI Editor:

1. Navigate to your Home Assistant dashboard.
2. Click on the three dots in the top right corner and select **"Configure UI"**.
3. Click on the **"Add Card"** button.
4. Add an **Entities Card**:
   - Select the **"Entities"** card.
   - Add your concerts entity (e.g., `text.setlistfm_user1_concerts`).

Example configuration:

```yaml
type: entities
title: Recent Concerts
entities:
  - entity: text.setlistfm_user1_concerts
    name: Recent Concerts
    secondary_info: last-changed
```

### Markdown Card
Open the Lovelace UI Editor:

1. Navigate to your Home Assistant dashboard.
2. Click on the three dots in the top right corner and select **"Configure UI"**.
3. Click on the **"Add Card"** button.
4. Add a **Markdown Card**:
   - Select the **"Markdown"** card.
   - Use the following template to display the contents of the concerts entity.

Example configuration:

```yaml
type: markdown
title: Recent Concerts
content: >
  {% set concerts = state_attr('text.setlistfm_user1_concerts', 'concert_list') %}
  {% if concerts %}
    **Recent Concerts:**
    {{ concerts }}
  {% else %}
    No concerts found.
  {% endif %}
```

## Force Refresh
You can manually force a refresh of the data by calling the `setlistfm.force_refresh` service in Home Assistant.

## Version

1.0 - 06/02/2025

## License
This project is licensed under the Apache 2.0 License. See the LICENSE file for details.


import logging
import requests
import json
import datetime
import time
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval
from homeassistant.util import dt as dt_util
from homeassistant.const import CONF_API_KEY
import os

DOMAIN = 'setlistfm'
CONF_REFRESH_PERIOD = 'refresh_period'
CONF_USERS = 'users'
CONF_USERID = 'userid'
CONF_NAME = 'name'
CONF_NUMBER_OF_CONCERTS = 'number_of_concerts'
CONF_DATE_FORMAT = 'date_format'
CONF_SHOW_CONCERTS = 'show_concerts'

DEFAULT_REFRESH_PERIOD = 6
DEFAULT_NUMBER_OF_CONCERTS = 10
DEFAULT_DATE_FORMAT = '%d-%m-%Y'
DEFAULT_SHOW_CONCERTS = 'all'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERS): vol.All(cv.ensure_list, [{
            vol.Required(CONF_USERID): cv.string,
            vol.Required(CONF_NAME): cv.string,
            vol.Required(CONF_API_KEY): cv.string,
            vol.Optional(CONF_REFRESH_PERIOD, default=DEFAULT_REFRESH_PERIOD): cv.positive_int,
            vol.Optional(CONF_NUMBER_OF_CONCERTS, default=DEFAULT_NUMBER_OF_CONCERTS): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
            vol.Optional(CONF_DATE_FORMAT, default=DEFAULT_DATE_FORMAT): vol.In(['%d-%m-%Y', '%d-%m-%y', '%m-%d-%Y', '%m-%d-%y']),
            vol.Optional(CONF_SHOW_CONCERTS, default=DEFAULT_SHOW_CONCERTS): vol.In(['upcoming', 'past', 'all']),
        }]),
    }),
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)

def setup(hass, config):
    _LOGGER.debug("Setting up Setlist.fm integration")
    conf = config[DOMAIN]
    users = conf[CONF_USERS]

    # Load translations
    translation_file = os.path.join(os.path.dirname(__file__), 'translations', 'en.json')
    with open(translation_file, 'r') as file:
        translations = json.load(file)
    at_str = translations.get('component', {}).get('setlistfm', {}).get('at', 'at')
    in_str = translations.get('component', {}).get('setlistfm', {}).get('in', 'in')
    on_str = translations.get('component', {}).get('setlistfm', {}).get('on', 'on')
    upcoming_str = translations.get('component', {}).get('setlistfm', {}).get('upcoming', 'Upcoming')

    def update_user_data(hass, api_key, userid, name, number_of_concerts, date_format, show_concerts):
        _LOGGER.debug(f"Updating data for user '{name}' with userid '{userid}'")
        headers = {
            'x-api-key': api_key,
            'Accept': 'application/json'
        }

        user_url = f"https://api.setlist.fm/rest/1.0/user/{userid}"
        _LOGGER.debug(f"Fetching user data from URL: {user_url}")
        response = requests.get(user_url, headers=headers)
        last_update_sensor = f"sensor.setlistfm_{name.lower()}_last_update"
        response_sensor = f"sensor.setlistfm_{name.lower()}_response"

        if response.status_code != 200:
            _LOGGER.error(f"Failed to fetch user data for '{name}': {response.status_code} - {response.text[:150]}")
            hass.states.set(last_update_sensor, dt_util.now().isoformat())
            hass.states.set(response_sensor, f"{response.status_code}: {response.text[:150]}")
            return

        _LOGGER.debug(f"Successfully fetched user data for '{name}'")
        _LOGGER.debug(f"User data response JSON: {response.json()}")  # Log the full JSON response

        attended_url = f"https://api.setlist.fm/rest/1.0/user/{userid}/attended"
        _LOGGER.debug(f"Fetching attended concerts data from URL: {attended_url}")

        # Retry logic for rate limiting
        retries = 3
        for attempt in range(retries):
            response = requests.get(attended_url, headers=headers)
            if response.status_code == 200:
                break
            elif response.status_code == 429:
                _LOGGER.error(f"Rate limit exceeded for '{name}', retrying in 5 seconds")
                time.sleep(5)  # Wait for 5 seconds before retrying
            else:
                _LOGGER.error(f"Failed to fetch attended concerts data for '{name}': {response.status_code} - {response.text[:150]}")
                hass.states.set(last_update_sensor, dt_util.now().isoformat())
                hass.states.set(response_sensor, f"{response.status_code}: {response.text[:150]}")
                return
        else:
            _LOGGER.error(f"Failed to fetch attended concerts data for '{name}' after {retries} attempts")
            hass.states.set(last_update_sensor, dt_util.now().isoformat())
            hass.states.set(response_sensor, f"{response.status_code}: {response.text[:150]}")
            return

        _LOGGER.debug(f"Successfully fetched attended concerts data for '{name}'")
        _LOGGER.debug(f"Attended concerts data response JSON: {response.json()}")  # Log the full JSON response

        concerts = response.json().get('setlist', [])
        concerts.sort(key=lambda x: datetime.datetime.strptime(x['eventDate'], '%d-%m-%Y'), reverse=True)  # Sort by date, newest first

        concert_list = []
        now = dt_util.now().date()
        for concert in concerts:
            event_date = datetime.datetime.strptime(concert['eventDate'], '%d-%m-%Y').date()
            formatted_date = event_date.strftime(date_format)
            artist_name = concert['artist']['name']
            venue_name = concert['venue']['name']
            city_name = concert['venue']['city']['name']
            line = f"{artist_name} {at_str} {venue_name}"
            if city_name:
                line += f" {in_str} {city_name}"
            line += f" {on_str} {formatted_date}"

            if show_concerts == 'upcoming' and event_date > now:
                if event_date > now:  # Compare dates
                    line += f" ({upcoming_str})"
                concert_list.append(line)
            elif show_concerts == 'past' and event_date <= now:
                concert_list.append(line)
            elif show_concerts == 'all':
                if event_date > now:
                    line += f" ({upcoming_str})"
                concert_list.append(line)

            if len(concert_list) >= number_of_concerts:
                break

            _LOGGER.debug(f"Built concert line: {line}")  # Log each concert line

        concert_text = "\n".join(concert_list)
        concerts_entity = f"text.setlistfm_{name.lower()}_concerts"

        _LOGGER.debug(f"Concert list for '{name}': {concert_list}")
        _LOGGER.debug(f"Setting state for entity '{concerts_entity}' with concert list")
        hass.states.set(last_update_sensor, dt_util.now().isoformat())
        hass.states.set(response_sensor, response.status_code)
        # Set the state to the number of concerts, and store the concert list in attributes
        hass.states.set(concerts_entity, len(concert_list), {
            'concert_list': concert_text
        })

        _LOGGER.debug(f"Updated state for user '{name}' with latest concerts data")

    def update_users(event_time):
        _LOGGER.debug("Updating all users' data")
        for user in users:
            api_key = user[CONF_API_KEY]
            userid = user[CONF_USERID]
            name = user[CONF_NAME]
            number_of_concerts = user.get(CONF_NUMBER_OF_CONCERTS, DEFAULT_NUMBER_OF_CONCERTS)
            date_format = user.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT)
            show_concerts = user.get(CONF_SHOW_CONCERTS, DEFAULT_SHOW_CONCERTS)
            update_user_data(hass, api_key, userid, name, number_of_concerts, date_format, show_concerts)

    for user in users:
        refresh_period = user.get(CONF_REFRESH_PERIOD, DEFAULT_REFRESH_PERIOD)
        _LOGGER.debug(f"Scheduling update for user '{user[CONF_NAME]}' every {refresh_period} hours")
        track_time_interval(hass, update_users, datetime.timedelta(hours=refresh_period))

    def force_refresh(call):
        _LOGGER.debug("Force refresh called")
        update_users(None)

    hass.services.register(DOMAIN, 'force_refresh', force_refresh)

    # Force a refresh on startup
    _LOGGER.debug("Forcing initial refresh on startup")
    update_users(None)

    return True

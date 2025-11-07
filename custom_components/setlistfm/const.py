"""Constants for the setlist.fm integration."""

DOMAIN = "setlistfm"

# Configuration
CONF_USERID = "userid"
CONF_API_KEY = "api_key"
CONF_NAME = "name"

# Options
CONF_REFRESH_PERIOD = "refresh_period"
CONF_NUMBER_OF_CONCERTS = "number_of_concerts"
CONF_DATE_FORMAT = "date_format"
CONF_SHOW_CONCERTS = "show_concerts"

# Defaults
DEFAULT_REFRESH_PERIOD = 6
DEFAULT_NUMBER_OF_CONCERTS = 10
DEFAULT_DATE_FORMAT = "%d-%m-%Y"
DEFAULT_SHOW_CONCERTS = "all"

# Date format options
DATE_FORMATS = {
    "%d-%m-%Y": "DD-MM-YYYY",
    "%d-%m-%y": "DD-MM-YY",
    "%m-%d-%Y": "MM-DD-YYYY",
    "%m-%d-%y": "MM-DD-YY",
}

# Show concerts options
SHOW_CONCERTS_OPTIONS = {
    "all": "All concerts",
    "upcoming": "Upcoming only",
    "past": "Past only",
}

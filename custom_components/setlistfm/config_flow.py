"""Config flow for setlist.fm integration."""
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_USERID,
    CONF_API_KEY,
    CONF_NAME,
    CONF_REFRESH_PERIOD,
    CONF_NUMBER_OF_CONCERTS,
    CONF_DATE_FORMAT,
    CONF_SHOW_CONCERTS,
    DEFAULT_REFRESH_PERIOD,
    DEFAULT_NUMBER_OF_CONCERTS,
    DEFAULT_DATE_FORMAT,
    DEFAULT_SHOW_CONCERTS,
    DATE_FORMATS,
    SHOW_CONCERTS_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    headers = {
        "x-api-key": data[CONF_API_KEY],
        "Accept": "application/json",
    }
    
    user_url = f"https://api.setlist.fm/rest/1.0/user/{data[CONF_USERID]}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(user_url, headers=headers) as response:
                if response.status == 401:
                    raise InvalidAuth
                elif response.status == 404:
                    raise UserNotFound
                elif response.status != 200:
                    raise CannotConnect
                
                user_data = await response.json()
                
                # Extract the username from the API response
                username = user_data.get("fullname") or user_data.get("userId") or data[CONF_USERID]
                
                return {"title": username, "user_data": user_data}
        
        except aiohttp.ClientError as err:
            _LOGGER.error("Error connecting to setlist.fm: %s", err)
            raise CannotConnect from err


class SetlistFmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for setlist.fm."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except UserNotFound:
                errors["base"] = "user_not_found"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Set unique ID to prevent duplicate entries for same user
                await self.async_set_unique_id(user_input[CONF_USERID])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_USERID: user_input[CONF_USERID],
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_NAME: user_input.get(CONF_NAME, info["title"]),
                    },
                    options={
                        CONF_REFRESH_PERIOD: DEFAULT_REFRESH_PERIOD,
                        CONF_NUMBER_OF_CONCERTS: DEFAULT_NUMBER_OF_CONCERTS,
                        CONF_DATE_FORMAT: DEFAULT_DATE_FORMAT,
                        CONF_SHOW_CONCERTS: DEFAULT_SHOW_CONCERTS,
                    },
                )
        
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERID): str,
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_NAME): str,
            }
        )
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return SetlistFmOptionsFlowHandler(config_entry)


class SetlistFmOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for setlist.fm integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        options = self._config_entry.options
        
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_REFRESH_PERIOD,
                    default=options.get(CONF_REFRESH_PERIOD, DEFAULT_REFRESH_PERIOD),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                vol.Optional(
                    CONF_NUMBER_OF_CONCERTS,
                    default=options.get(CONF_NUMBER_OF_CONCERTS, DEFAULT_NUMBER_OF_CONCERTS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
                vol.Optional(
                    CONF_DATE_FORMAT,
                    default=options.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT),
                ): vol.In(DATE_FORMATS),
                vol.Optional(
                    CONF_SHOW_CONCERTS,
                    default=options.get(CONF_SHOW_CONCERTS, DEFAULT_SHOW_CONCERTS),
                ): vol.In(SHOW_CONCERTS_OPTIONS),
            }
        )
        
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class UserNotFound(HomeAssistantError):
    """Error to indicate the user was not found."""

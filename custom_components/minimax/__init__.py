"""The MiniMax integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import MiniMaxApiClient, MiniMaxApiClientError
from .const import DOMAIN, LOGGER, PLATFORMS

type MiniMaxConfigEntry = ConfigEntry[MiniMaxApiClient]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up MiniMax integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MiniMaxConfigEntry) -> bool:
    """Set up MiniMax from a config entry."""
    api_key = entry.data.get(CONF_API_KEY)

    client = MiniMaxApiClient(
        api_key=api_key,
        session=async_get_clientsession(hass),
    )

    try:
        await client.async_verify_connection()
    except MiniMaxApiClientError as err:
        err_str = str(err)
        if (
            "401" in err_str
            or "authentication" in err_str.lower()
            or "api_key" in err_str.lower()
            or "invalid api key" in err_str.lower()
        ):
            raise ConfigEntryAuthFailed("Invalid API key") from err
        raise ConfigEntryNotReady(f"Failed to connect to MiniMax API: {err}") from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: MiniMaxConfigEntry) -> None:
    """Reload entry when options or subentries change."""
    LOGGER.debug("Reloading MiniMax entry due to options/subentry change")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MiniMaxConfigEntry) -> bool:
    """Unload MiniMax entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: MiniMaxConfigEntry) -> bool:
    """Migrate entry."""
    LOGGER.debug("Migrating from version %s:%s", entry.version, entry.minor_version)
    return True

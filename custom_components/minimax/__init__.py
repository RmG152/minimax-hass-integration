"""The MiniMax integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import MiniMaxApiClient
from .const import LOGGER, PLATFORMS

type MiniMaxConfigEntry = ConfigEntry[MiniMaxApiClient]


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
    except Exception as err:
        if "401" in str(err) or "authentication" in str(err).lower():
            raise ConfigEntryAuthFailed("Invalid API key") from err
        raise ConfigEntryNotReady(f"Failed to connect to MiniMax API: {err}") from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MiniMaxConfigEntry) -> bool:
    """Unload MiniMax entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: MiniMaxConfigEntry) -> bool:
    """Migrate entry."""
    LOGGER.debug("Migrating from version %s:%s", entry.version, entry.minor_version)
    return True

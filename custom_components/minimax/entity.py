"""Base entity for MiniMax integration."""

from homeassistant.config_entries import ConfigEntry, ConfigSubentry

from .api import MiniMaxApiClient


class MiniMaxBaseEntity:
    """Mixin for MiniMax entities backed by a config subentry.

    Provides the common ``entry``, ``subentry``, ``_client`` storage and
    sets ``_attr_has_entity_name``, ``_attr_name`` and ``_attr_unique_id``
    consistently across Conversation, STT, TTS and AI Task entities.
    """

    _attr_has_entity_name = True

    entry: ConfigEntry
    subentry: ConfigSubentry

    def __init__(
        self,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        client: MiniMaxApiClient,
    ) -> None:
        """Initialize common entity attributes."""
        self.entry = entry
        self.subentry = subentry
        self._client = client
        self._attr_name = subentry.title
        self._attr_unique_id = subentry.subentry_id

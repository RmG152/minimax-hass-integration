"""Text to speech support for MiniMax."""

from collections.abc import Mapping
import logging
from typing import Any

from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import MiniMaxApiClient
from .const import (
    CONF_LANGUAGE_BOOST,
    CONF_PITCH,
    CONF_SPEED,
    CONF_TTS_MODEL,
    CONF_VOL,
    DEFAULT_LANGUAGE_BOOST,
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    DEFAULT_VOL,
    RECOMMENDED_TTS_MODEL,
    VOICE_IDS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TTS entities."""
    client = config_entry.runtime_data

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "tts":
            continue

        async_add_entities(
            [MiniMaxTTSEntity(config_entry, subentry, client)],
            config_subentry_id=subentry.subentry_id,
        )


class MiniMaxTTSEntity(TextToSpeechEntity):
    """MiniMax text-to-speech entity."""

    _attr_supported_options = [ATTR_VOICE]
    _attr_supported_languages = list(VOICE_IDS.keys())
    _attr_default_language = "en-US"

    def __init__(
        self,
        config_entry: ConfigEntry,
        subentry: ConfigSubentry,
        client: MiniMaxApiClient,
    ) -> None:
        """Initialize the TTS entity."""
        self.entry = config_entry
        self.subentry = subentry
        self._client = client
        self._attr_name = subentry.title
        self._attr_unique_id = subentry.subentry_id

    @cached_property
    def default_options(self) -> Mapping[str, Any]:
        """Return a mapping with the default options."""
        voices = self.async_get_supported_voices(self._attr_default_language)
        return {ATTR_VOICE: voices[0].voice_id if voices else ""}

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        if language not in VOICE_IDS:
            return None
        return [
            Voice(
                voice_id=voice_id,
                name=voice_id.replace("_", " ").replace("-", " ").title(),
            )
            for voice_id in VOICE_IDS.get(language, [])
        ]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load TTS audio from the engine."""
        _LOGGER.debug(
            "TTS request: message_length=%d, language=%s", len(message), language
        )
        voice_id = options[ATTR_VOICE]
        speed = options.get(
            CONF_SPEED, self.subentry.data.get(CONF_SPEED, DEFAULT_SPEED)
        )
        vol = options.get(CONF_VOL, self.subentry.data.get(CONF_VOL, DEFAULT_VOL))
        pitch = options.get(
            CONF_PITCH, self.subentry.data.get(CONF_PITCH, DEFAULT_PITCH)
        )
        language_boost = self.subentry.data.get(
            CONF_LANGUAGE_BOOST, DEFAULT_LANGUAGE_BOOST
        )
        _LOGGER.debug(
            "TTS options: voice=%s, speed=%s, vol=%s, pitch=%s, language_boost=%s",
            voice_id,
            speed,
            vol,
            pitch,
            language_boost,
        )

        try:
            audio_data = await self._client.async_tts(
                text=message,
                voice_id=voice_id,
                speed=speed,
                vol=vol,
                pitch=int(pitch),
                model=self.subentry.data.get(CONF_TTS_MODEL, RECOMMENDED_TTS_MODEL),
                language_boost=language_boost or None,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error during TTS: %s", err)
            return (None, None)
        else:
            _LOGGER.debug("TTS generated %d bytes of audio", len(audio_data))
            return ("mp3", audio_data)

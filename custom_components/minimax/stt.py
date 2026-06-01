"""Speech to text support for MiniMax."""

from collections.abc import AsyncIterable
import logging

from homeassistant.components import stt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CHAT_MODEL, CONF_PROMPT, RECOMMENDED_CHAT_MODEL
from .entity import MiniMaxBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up STT entities."""
    client = config_entry.runtime_data

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "stt":
            continue

        async_add_entities(
            [MiniMaxSTTEntity(config_entry, subentry, client)],
            config_subentry_id=subentry.subentry_id,
        )


class MiniMaxSTTEntity(MiniMaxBaseEntity, stt.SpeechToTextEntity):
    """MiniMax speech-to-text entity."""

    _attr_supported_languages = ["en-US", "zh-CN"]

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self._attr_supported_languages

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        return [stt.AudioFormats.WAV, stt.AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM, stt.AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bit rates."""
        return [stt.AudioBitRates.BITRATE_16, stt.AudioBitRates.BITRATE_32]

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [
            stt.AudioSampleRates.SAMPLERATE_16000,
            stt.AudioSampleRates.SAMPLERATE_32000,
        ]

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        return [stt.AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Process an audio stream to STT service."""
        _LOGGER.debug("Processing STT audio stream, language: %s", metadata.language)
        prompt = self.subentry.data.get(CONF_PROMPT, "Transcribe the audio")
        model = self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)

        audio_data = b""
        async for chunk in stream:
            audio_data += chunk
        _LOGGER.debug("Received %d bytes of audio data", len(audio_data))

        try:
            text = await self._client.async_stt(
                audio_data=audio_data,
                model=model,
                language=metadata.language,
                prompt=prompt,
                audio_format=metadata.format.value,
            )
            _LOGGER.debug("STT result length: %d", len(text) if text else 0)
            if text:
                return stt.SpeechResult(text, stt.SpeechResultState.SUCCESS)

            _LOGGER.warning("STT returned empty text")
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error during STT: %s", err)
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

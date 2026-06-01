"""Text to speech support for MiniMax."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Mapping
import contextlib
import logging
import re
from typing import Any

from propcache.api import cached_property
from sentence_stream import SentenceBoundaryDetector

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TTSAudioRequest,
    TTSAudioResponse,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_LANGUAGE_BOOST,
    CONF_PITCH,
    CONF_SPEED,
    CONF_STREAMING_FORMAT,
    CONF_TTS_MODEL,
    CONF_VOL,
    DEFAULT_LANGUAGE_BOOST,
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    DEFAULT_STREAMING_FORMAT,
    DEFAULT_VOL,
    RECOMMENDED_TTS_MODEL,
    VOICE_IDS,
)
from .entity import MiniMaxBaseEntity
from .websocket_client import MiniMaxT2AWebSocketClient

_LOGGER = logging.getLogger(__name__)

_CJK_TERMINATORS = re.compile(r"(?<=[。！？\n])")


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


class MiniMaxTTSEntity(MiniMaxBaseEntity, TextToSpeechEntity):
    """MiniMax text-to-speech entity."""

    _attr_supported_options = [ATTR_VOICE]
    _attr_supported_languages = list(VOICE_IDS.keys())
    _attr_default_language = "en-US"

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
        vol = min(
            float(options.get(CONF_VOL, self.subentry.data.get(CONF_VOL, DEFAULT_VOL))),
            1.0,
        )
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

    async def async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse:
        """Stream TTS audio via MiniMax WebSocket for streaming text input."""
        return TTSAudioResponse(
            self._resolve_streaming_format(request.options),
            self._process_tts_stream(request),
        )

    def _resolve_streaming_format(self, options: Mapping[str, Any]) -> str:
        """Pick the audio format. Option override first, then subentry data, then default."""
        if options.get(CONF_STREAMING_FORMAT) is not None:
            return options[CONF_STREAMING_FORMAT]
        return self.subentry.data.get(CONF_STREAMING_FORMAT, DEFAULT_STREAMING_FORMAT)

    async def _process_tts_stream(
        self, request: TTSAudioRequest
    ) -> AsyncGenerator[bytes]:
        """Accumulate text into sentences, stream audio chunks per sentence."""
        sentences: asyncio.Queue[str | None] = asyncio.Queue()
        feed_task = asyncio.create_task(
            self._feed_detector(request, sentences),
            name="minimax_tts_feed_detector",
        )
        ws_client = self._build_ws_client(request)
        try:
            async for audio_chunk in ws_client.stream(self._drain_sentences(sentences)):
                yield audio_chunk
        finally:
            await self._cancel_feed(feed_task)

    async def _feed_detector(
        self,
        request: TTSAudioRequest,
        sentences: asyncio.Queue[str | None],
    ) -> None:
        """Read message chunks, split into sentences, enqueue them."""
        detector = SentenceBoundaryDetector()
        try:
            async for chunk in request.message_gen:
                for sentence in detector.add_chunk(chunk):
                    cleaned = self._postprocess_sentence(sentence)
                    if cleaned:
                        await sentences.put(cleaned)
            tail = detector.finish()
            cleaned_tail = self._postprocess_sentence(tail) if tail else ""
            if cleaned_tail:
                await sentences.put(cleaned_tail)
        finally:
            await sentences.put(None)

    @staticmethod
    async def _drain_sentences(
        sentences: asyncio.Queue[str | None],
    ) -> AsyncIterator[str]:
        """Yield sentences from the queue until the sentinel None is seen."""
        while True:
            sentence = await sentences.get()
            if sentence is None:
                return
            yield sentence

    def _build_ws_client(self, request: TTSAudioRequest) -> MiniMaxT2AWebSocketClient:
        """Construct the WebSocket TTS client from subentry + request options."""
        subentry_data = self.subentry.data
        return MiniMaxT2AWebSocketClient(
            hass=self.hass,
            api_key=self._client.api_key,
            model=subentry_data.get(CONF_TTS_MODEL, RECOMMENDED_TTS_MODEL),
            voice_id=request.options.get(ATTR_VOICE, self.default_options[ATTR_VOICE]),
            language_boost=subentry_data.get(
                CONF_LANGUAGE_BOOST, DEFAULT_LANGUAGE_BOOST
            )
            or None,
            speed=float(subentry_data.get(CONF_SPEED, DEFAULT_SPEED)),
            vol=min(float(subentry_data.get(CONF_VOL, DEFAULT_VOL)), 1.0),
            pitch=int(subentry_data.get(CONF_PITCH, DEFAULT_PITCH)),
            audio_format=self._resolve_streaming_format(request.options),
        )

    @staticmethod
    async def _cancel_feed(feed_task: asyncio.Task[None]) -> None:
        """Cancel the feed task and swallow the CancelledError."""
        if feed_task.done():
            return
        feed_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await feed_task

    @staticmethod
    def _postprocess_sentence(sentence: str) -> str:
        """Re-split sentences on fullwidth CJK terminators.

        ``sentence_stream.SentenceBoundaryDetector`` only knows about Latin
        punctuation. Chinese/Japanese sentences ending in 。！？ arrive as
        one chunk (no preceding ASCII punctuation), so we re-split here to
        give CJK users per-sentence streaming latency.
        """
        if "。" in sentence or "！" in sentence or "？" in sentence:
            parts = _CJK_TERMINATORS.split(sentence)
            cleaned = [p.strip() for p in parts if p.strip()]
            if len(cleaned) > 1:
                return " ".join(cleaned)
        return sentence.strip()

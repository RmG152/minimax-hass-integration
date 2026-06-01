"""Tests for MiniMax TTS entity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.minimax import tts as minimax_tts
from custom_components.minimax.const import (
    CONF_PITCH,
    CONF_SPEED,
    CONF_STREAMING_FORMAT,
    CONF_TTS_MODEL,
    CONF_VOL,
    DEFAULT_STREAMING_FORMAT,
    RECOMMENDED_TTS_MODEL,
    RECOMMENDED_TTS_OPTIONS,
    VOICE_IDS,
)
from homeassistant.components.tts import ATTR_VOICE, Voice
from homeassistant.exceptions import HomeAssistantError


def _make_subentry(data=None, title=None):
    """Create a mock TTS subentry."""
    subentry = MagicMock()
    subentry.subentry_id = "tts_subentry_001"
    subentry.subentry_type = "tts"
    subentry.title = title or "MiniMax TTS"
    subentry.data = data or RECOMMENDED_TTS_OPTIONS.copy()
    return subentry


def _make_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"api_key": "test_key"}
    entry.subentries = {}
    return entry


class TestMiniMaxTTSEntity:
    """Test MiniMaxTTSEntity."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        from tests import TTS_RESPONSE_BYTES, create_mock_minimax_client

        client = create_mock_minimax_client()
        client.async_tts = AsyncMock(return_value=TTS_RESPONSE_BYTES)
        return client

    @pytest.fixture
    def entity(self, mock_client):
        """Create a TTS entity for testing."""
        entry = _make_config_entry()
        subentry = _make_subentry()
        return minimax_tts.MiniMaxTTSEntity(
            entry=entry,
            subentry=subentry,
            client=mock_client,
        )

    def test_entity_properties(self, entity):
        """Test entity properties are set correctly."""
        assert entity._attr_name == "MiniMax TTS"
        assert entity._attr_unique_id == "tts_subentry_001"
        assert entity._attr_default_language == "en-US"

    def test_supported_options(self, entity):
        """Test supported_options returns correct options."""
        assert ATTR_VOICE in entity.supported_options

    def test_supported_languages(self, entity):
        """Test supported_languages returns correct languages."""
        for lang in VOICE_IDS:
            assert lang in entity.supported_languages

    def test_default_options(self, entity):
        """Test default_options returns correct options."""
        options = entity.default_options
        assert ATTR_VOICE in options
        assert options[ATTR_VOICE] == VOICE_IDS["en-US"][0]

    def test_async_get_supported_voices_for_en(self, entity):
        """Test async_get_supported_voices returns voices for en-US."""
        voices = entity.async_get_supported_voices("en-US")
        assert isinstance(voices, list)
        assert len(voices) > 0
        for voice in voices:
            assert isinstance(voice, Voice)
            assert voice.voice_id in VOICE_IDS["en-US"]

    def test_async_get_supported_voices_for_unsupported(self, entity):
        """Test async_get_supported_voices returns None for unsupported."""
        assert entity.async_get_supported_voices("xx-XX") is None

    def test_async_get_supported_voices_for_chinese(self, entity):
        """Test async_get_supported_voices returns voices for zh-CN."""
        voices = entity.async_get_supported_voices("zh-CN")
        assert isinstance(voices, list)
        assert len(voices) > 0
        for voice in voices:
            assert voice.voice_id in VOICE_IDS["zh-CN"]

    @pytest.mark.asyncio
    async def test_async_get_tts_audio_success(self, entity, mock_client):
        """Test async_get_tts_audio returns successful audio."""
        from tests import TTS_RESPONSE_BYTES

        result = await entity.async_get_tts_audio(
            message="Hello world",
            language="en-US",
            options={ATTR_VOICE: "English_PlayfulGirl"},
        )

        assert result[0] == "mp3"
        assert result[1] == TTS_RESPONSE_BYTES

    @pytest.mark.asyncio
    async def test_async_get_tts_audio_custom_options(self, entity, mock_client):
        """Test async_get_tts_audio passes custom options to client."""
        await entity.async_get_tts_audio(
            message="Hello",
            language="en-US",
            options={
                ATTR_VOICE: "English_Narrator",
                CONF_SPEED: 1.5,
                CONF_VOL: 0.8,
                CONF_PITCH: 2,
            },
        )

        mock_client.async_tts.assert_called_once()
        kwargs = mock_client.async_tts.call_args[1]
        assert kwargs["voice_id"] == "English_Narrator"
        assert kwargs["speed"] == 1.5
        assert kwargs["vol"] == 0.8
        assert kwargs["pitch"] == 2

    @pytest.mark.asyncio
    async def test_async_get_tts_audio_error(self, entity, mock_client):
        """Test async_get_tts_audio handles errors gracefully."""
        mock_client.async_tts = AsyncMock(side_effect=Exception("API Error"))

        result = await entity.async_get_tts_audio(
            message="Hello",
            language="en-US",
            options={ATTR_VOICE: "English_PlayfulGirl"},
        )

        assert result[0] is None
        assert result[1] is None

    @pytest.mark.asyncio
    async def test_async_get_tts_audio_subentry_defaults(self, entity, mock_client):
        """Test async_get_tts_audio uses subentry default options."""
        await entity.async_get_tts_audio(
            message="Hello",
            language="en-US",
            options={ATTR_VOICE: VOICE_IDS["en-US"][0]},
        )

        mock_client.async_tts.assert_called_once()
        kwargs = mock_client.async_tts.call_args[1]
        assert kwargs["voice_id"] == VOICE_IDS["en-US"][0]
        assert kwargs["speed"] == RECOMMENDED_TTS_OPTIONS[CONF_SPEED]
        assert kwargs["vol"] == RECOMMENDED_TTS_OPTIONS[CONF_VOL]
        assert kwargs["pitch"] == RECOMMENDED_TTS_OPTIONS[CONF_PITCH]
        assert kwargs["model"] == RECOMMENDED_TTS_MODEL

    @pytest.mark.asyncio
    async def test_async_get_tts_audio_custom_model(self, mock_client):
        """Test async_get_tts_audio uses custom tts_model from subentry."""

        entry = _make_config_entry()
        subentry_data = RECOMMENDED_TTS_OPTIONS.copy()
        subentry_data[CONF_TTS_MODEL] = "speech-2.8-turbo"
        subentry = _make_subentry(data=subentry_data)
        entity = minimax_tts.MiniMaxTTSEntity(
            entry=entry,
            subentry=subentry,
            client=mock_client,
        )

        await entity.async_get_tts_audio(
            message="Hello",
            language="en-US",
            options={ATTR_VOICE: "English_PlayfulGirl"},
        )

        mock_client.async_tts.assert_called_once()
        kwargs = mock_client.async_tts.call_args[1]
        assert kwargs["model"] == "speech-2.8-turbo"


class TestTTSSetup:
    """Test TTS platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_entity(self, hass):
        """Test async_setup_entry creates TTS entity."""
        from tests import create_mock_minimax_client

        entry = _make_config_entry()
        subentry = _make_subentry()
        entry.subentries = {"tts": subentry}
        entry.runtime_data = create_mock_minimax_client()

        entities_added = []

        def mock_add_entities(entities, config_subentry_id=None):
            entities_added.extend(entities)

        await minimax_tts.async_setup_entry(hass, entry, mock_add_entities)

        assert len(entities_added) == 1
        assert entities_added[0]._attr_name == "MiniMax TTS"

    @pytest.mark.asyncio
    async def test_async_setup_entry_skips_non_tts(self, hass):
        """Test async_setup_entry skips non-TTS subentries."""
        from tests import create_mock_minimax_client

        entry = _make_config_entry()
        subentry = MagicMock()
        subentry.subentry_id = "conv_001"
        subentry.subentry_type = "conversation"
        subentry.title = "MiniMax Conversation"
        subentry.data = {}
        entry.subentries = {"conversation": subentry}
        entry.runtime_data = create_mock_minimax_client()

        entities_added = []

        def mock_add_entities(entities, config_subentry_id=None):
            entities_added.extend(entities)

        await minimax_tts.async_setup_entry(hass, entry, mock_add_entities)

        assert len(entities_added) == 0


class TestTTSStreaming:
    """Test streaming TTS via WebSocket."""

    def _make_entity(self, hass, subentry_data=None):
        from tests import create_mock_minimax_client

        client = create_mock_minimax_client()
        client.api_key = "test-key-123"
        entry = _make_config_entry()
        subentry = _make_subentry(data=subentry_data or {})
        entry.subentries = {"tts": subentry}
        entry.runtime_data = client
        entity = minimax_tts.MiniMaxTTSEntity(entry, subentry, client)
        entity.hass = hass
        return entity

    def _make_request(self, chunks, voice="en-US-female-1", options=None):
        from homeassistant.components.tts import TTSAudioRequest

        async def gen():
            for c in chunks:
                yield c

        return TTSAudioRequest(
            message_gen=gen(),
            language="en",
            options={ATTR_VOICE: voice, **(options or {})},
        )

    @pytest.mark.asyncio
    async def test_supports_streaming_input_returns_true(self, hass):
        """MiniMax TTS supports streaming input."""
        entity = self._make_entity(hass)
        assert entity.async_supports_streaming_input() is True

    def test_resolve_streaming_format_prefers_option(self, hass):
        """Per-call option override beats subentry data."""
        entity = self._make_entity(hass, subentry_data={CONF_STREAMING_FORMAT: "pcm"})
        assert (
            entity._resolve_streaming_format({CONF_STREAMING_FORMAT: "opus"}) == "opus"
        )

    def test_resolve_streaming_format_falls_back_to_subentry(self, hass):
        """Falls back to subentry data when option is absent."""
        entity = self._make_entity(hass, subentry_data={CONF_STREAMING_FORMAT: "pcm"})
        assert entity._resolve_streaming_format({}) == "pcm"

    def test_resolve_streaming_format_default(self, hass):
        """Falls back to DEFAULT_STREAMING_FORMAT."""
        entity = self._make_entity(hass, subentry_data={})
        assert entity._resolve_streaming_format({}) == DEFAULT_STREAMING_FORMAT

    def test_postprocess_sentence_strips_latin(self, hass):
        """Latin sentences pass through (stripped)."""
        result = minimax_tts.MiniMaxTTSEntity._postprocess_sentence("Hello world.")
        assert result == "Hello world."

    def test_postprocess_sentence_splits_cjk(self, hass):
        """CJK sentences ending in 。！？ get re-split."""
        result = minimax_tts.MiniMaxTTSEntity._postprocess_sentence(
            "你好。今天天气真好！明天会更好吗？"
        )
        assert "你好。" in result
        assert "今天天气真好！" in result
        assert "明天会更好吗？" in result
        assert result.count("。") + result.count("！") + result.count("？") >= 2

    def test_postprocess_sentence_no_cjk_returns_stripped(self, hass):
        """If no CJK terminator present, return stripped sentence as-is."""
        result = minimax_tts.MiniMaxTTSEntity._postprocess_sentence("  plain text  ")
        assert result == "plain text"

    @pytest.mark.asyncio
    async def test_streaming_picks_option_format(self, hass):
        """async_stream_tts_audio uses option format when provided."""
        entity = self._make_entity(hass, subentry_data={CONF_STREAMING_FORMAT: "mp3"})
        request = self._make_request(
            chunks=["Hello."], options={CONF_STREAMING_FORMAT: "opus"}
        )

        with patch.object(
            minimax_tts.MiniMaxT2AWebSocketClient, "stream"
        ) as mock_stream:
            mock_stream.return_value = _async_iter([b"\x00\x01"])
            response = await entity.async_stream_tts_audio(request)
            chunks = [chunk async for chunk in response.data_gen]

        assert response.extension == "opus"
        assert chunks == [b"\x00\x01"]

    @pytest.mark.asyncio
    async def test_streaming_falls_back_to_subentry_format(self, hass):
        """async_stream_tts_audio uses subentry format when option is absent."""
        entity = self._make_entity(hass, subentry_data={CONF_STREAMING_FORMAT: "pcm"})
        request = self._make_request(chunks=["Hello."], options={})

        with patch.object(
            minimax_tts.MiniMaxT2AWebSocketClient, "stream"
        ) as mock_stream:
            mock_stream.return_value = _async_iter([b"\x00\x01"])
            response = await entity.async_stream_tts_audio(request)

        assert response.extension == "pcm"

    @pytest.mark.asyncio
    async def test_streaming_sends_sentence_chunks(self, hass):
        """WebSocket receives one chunk per complete sentence."""
        entity = self._make_entity(hass)
        request = self._make_request(chunks=["Hello world. "])

        captured_sentences: list[str] = []

        async def fake_stream(self, sentences):
            async for sentence in sentences:
                captured_sentences.append(sentence)
                yield b"audio"

        with patch.object(
            minimax_tts.MiniMaxT2AWebSocketClient, "stream", new=fake_stream
        ):
            response = await entity.async_stream_tts_audio(request)
            _ = [chunk async for chunk in response.data_gen]

        assert "Hello world." in captured_sentences

    @pytest.mark.asyncio
    async def test_streaming_propagates_home_assistant_error(self, hass):
        """HomeAssistantError from the WebSocket client propagates to caller."""
        entity = self._make_entity(hass)
        request = self._make_request(chunks=["Hi."])

        async def fake_stream(self, sentences):
            yield b""  # mark as async generator; raises on next __anext__
            raise HomeAssistantError("WS boom")

        with patch.object(
            minimax_tts.MiniMaxT2AWebSocketClient, "stream", new=fake_stream
        ):
            response = await entity.async_stream_tts_audio(request)
            with pytest.raises(HomeAssistantError, match="WS boom"):
                _ = [chunk async for chunk in response.data_gen]

    @pytest.mark.asyncio
    async def test_streaming_splits_cjk_sentences(self, hass):
        """CJK text gets re-split into multiple sentence chunks."""
        entity = self._make_entity(hass)
        request = self._make_request(chunks=["你好。世界。"])

        captured_sentences: list[str] = []

        async def fake_stream(self, sentences):
            async for sentence in sentences:
                captured_sentences.append(sentence)
                yield b"audio"

        with patch.object(
            minimax_tts.MiniMaxT2AWebSocketClient, "stream", new=fake_stream
        ):
            response = await entity.async_stream_tts_audio(request)
            _ = [chunk async for chunk in response.data_gen]

        joined = " ".join(captured_sentences)
        assert "你好。" in joined
        assert "世界。" in joined
        assert len(captured_sentences) >= 2


def _async_iter(items):
    """Helper: turn a list into an async iterator."""

    async def _aiter():
        for item in items:
            yield item

    return _aiter()

"""Tests for MiniMax STT entity."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.minimax import stt as minimax_stt
from custom_components.minimax.const import RECOMMENDED_STT_OPTIONS
from homeassistant.components import stt


def _make_subentry(data=None, title=None):
    """Create a mock STT subentry."""
    subentry = MagicMock()
    subentry.subentry_id = "stt_subentry_001"
    subentry.subentry_type = "stt"
    subentry.title = title or "MiniMax STT"
    subentry.data = data or RECOMMENDED_STT_OPTIONS.copy()
    return subentry


def _make_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"api_key": "test_key"}
    entry.subentries = {}
    return entry


async def _async_gen(data: bytes, chunk_size: int = 1024):
    """Create an async generator from bytes."""
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


class TestMiniMaxSTTEntity:
    """Test MiniMaxSTTEntity."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        from tests import STT_RESPONSE_TEXT, create_mock_minimax_client

        client = create_mock_minimax_client()
        client.async_stt = AsyncMock(return_value=STT_RESPONSE_TEXT)
        return client

    @pytest.fixture
    def entity(self, mock_client):
        """Create an STT entity for testing."""
        entry = _make_config_entry()
        subentry = _make_subentry()
        return minimax_stt.MiniMaxSTTEntity(
            config_entry=entry,
            subentry=subentry,
            client=mock_client,
        )

    def test_entity_properties(self, entity):
        """Test entity properties are set correctly."""
        assert entity._attr_name == "MiniMax STT"
        assert entity._attr_unique_id == "stt_subentry_001"

    def test_supported_languages(self, entity):
        """Test supported_languages returns correct languages."""
        assert "en-US" in entity.supported_languages
        assert "zh-CN" in entity.supported_languages

    def test_supported_formats(self, entity):
        """Test supported_formats returns correct formats."""
        assert stt.AudioFormats.WAV in entity.supported_formats
        assert stt.AudioFormats.OGG in entity.supported_formats

    def test_supported_codecs(self, entity):
        """Test supported_codecs returns correct codecs."""
        assert stt.AudioCodecs.PCM in entity.supported_codecs
        assert stt.AudioCodecs.OPUS in entity.supported_codecs

    def test_supported_bit_rates(self, entity):
        """Test supported_bit_rates returns correct bit rates."""
        assert stt.AudioBitRates.BITRATE_16 in entity.supported_bit_rates
        assert stt.AudioBitRates.BITRATE_32 in entity.supported_bit_rates

    def test_supported_sample_rates(self, entity):
        """Test supported_sample_rates returns correct sample rates."""
        assert stt.AudioSampleRates.SAMPLERATE_16000 in entity.supported_sample_rates
        assert stt.AudioSampleRates.SAMPLERATE_32000 in entity.supported_sample_rates

    def test_supported_channels(self, entity):
        """Test supported_channels returns correct channels."""
        assert stt.AudioChannels.CHANNEL_MONO in entity.supported_channels

    @pytest.mark.asyncio
    async def test_async_process_audio_stream_success(self, entity, mock_client):
        """Test async_process_audio_stream returns successful transcription."""
        from tests import STT_RESPONSE_TEXT

        metadata = stt.SpeechMetadata(
            language="en-US",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )

        result = await entity.async_process_audio_stream(metadata, _async_gen(b"audio"))

        assert result.text == STT_RESPONSE_TEXT
        assert result.result == stt.SpeechResultState.SUCCESS
        mock_client.async_stt.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_process_audio_stream_empty(self, entity, mock_client):
        """Test async_process_audio_stream with empty transcription."""
        mock_client.async_stt = AsyncMock(return_value="")

        metadata = stt.SpeechMetadata(
            language="en-US",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )

        result = await entity.async_process_audio_stream(metadata, _async_gen(b"audio"))

        assert result.text is None
        assert result.result == stt.SpeechResultState.ERROR

    @pytest.mark.asyncio
    async def test_async_process_audio_stream_error(self, entity, mock_client):
        """Test async_process_audio_stream handles API errors."""
        mock_client.async_stt = AsyncMock(side_effect=Exception("API Error"))

        metadata = stt.SpeechMetadata(
            language="en-US",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )

        result = await entity.async_process_audio_stream(metadata, _async_gen(b"audio"))

        assert result.text is None
        assert result.result == stt.SpeechResultState.ERROR

    @pytest.mark.asyncio
    async def test_async_process_audio_stream_passes_params(self, entity, mock_client):
        """Test async_process_audio_stream passes correct params to client."""
        metadata = stt.SpeechMetadata(
            language="en-US",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )

        await entity.async_process_audio_stream(metadata, _async_gen(b"test_audio"))

        mock_client.async_stt.assert_called_once()
        kwargs = mock_client.async_stt.call_args[1]
        assert kwargs["language"] == "en-US"
        assert kwargs["audio_format"] == "wav"
        assert kwargs["audio_data"] == b"test_audio"


class TestSTTSetup:
    """Test STT platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_entity(self, hass):
        """Test async_setup_entry creates STT entity."""
        from tests import create_mock_minimax_client

        entry = _make_config_entry()
        subentry = _make_subentry()
        entry.subentries = {"stt": subentry}
        entry.runtime_data = create_mock_minimax_client()

        entities_added = []

        def mock_add_entities(entities, config_subentry_id=None):
            entities_added.extend(entities)

        await minimax_stt.async_setup_entry(hass, entry, mock_add_entities)

        assert len(entities_added) == 1
        assert entities_added[0]._attr_name == "MiniMax STT"

    @pytest.mark.asyncio
    async def test_async_setup_entry_skips_non_stt(self, hass):
        """Test async_setup_entry skips non-STT subentries."""
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

        await minimax_stt.async_setup_entry(hass, entry, mock_add_entities)

        assert len(entities_added) == 0

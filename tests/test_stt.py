"""Tests for MiniMax STT entity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.minimax import stt as minimax_stt
from custom_components.minimax.const import RECOMMENDED_STT_OPTIONS
from homeassistant.components import stt
from homeassistant.core import HomeAssistant
from tests import (  # noqa: TID251
    STT_RESPONSE_TEXT,
    create_mock_minimax_client,
    create_mock_minimax_config_entry,
)

pytest_plugins = "pytest_homeassistant_custom_component"


class TestMiniMaxSTTEntity:
    """Test MiniMaxSTTEntity."""

    @pytest.fixture
    def mock_config_entry_with_stt_subentry(self, hass: HomeAssistant):
        """Create a config entry with an STT subentry."""
        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "stt_subentry_001"
        subentry.subentry_type = "stt"
        subentry.title = "MiniMax STT"
        subentry.data = RECOMMENDED_STT_OPTIONS.copy()
        config_entry.subentries = {"stt": subentry}
        return config_entry

    @pytest.fixture
    def mock_stt_entity(self, mock_config_entry_with_stt_subentry, hass: HomeAssistant):
        """Create an STT entity for testing."""
        mock_client = create_mock_minimax_client()
        entity = minimax_stt.MiniMaxSTTEntity(
            config_entry=mock_config_entry_with_stt_subentry,
            subentry=mock_config_entry_with_stt_subentry.subentries["stt"],
            client=mock_client,
        )
        entity.hass = hass
        return entity

    def test_entity_properties(self, mock_stt_entity):
        """Test entity properties are set correctly."""
        assert mock_stt_entity._attr_name == "MiniMax STT"  # noqa: SLF001
        assert mock_stt_entity._attr_unique_id == "stt_subentry_001"  # noqa: SLF001

    def test_supported_languages(self, mock_stt_entity):
        """Test supported_languages returns correct languages."""
        assert "en-US" in mock_stt_entity.supported_languages
        assert "zh-CN" in mock_stt_entity.supported_languages

    def test_supported_formats(self, mock_stt_entity):
        """Test supported_formats returns correct formats."""
        assert stt.AudioFormats.WAV in mock_stt_entity.supported_formats
        assert stt.AudioFormats.OGG in mock_stt_entity.supported_formats

    def test_supported_codecs(self, mock_stt_entity):
        """Test supported_codecs returns correct codecs."""
        assert stt.AudioCodecs.PCM in mock_stt_entity.supported_codecs
        assert stt.AudioCodecs.OPUS in mock_stt_entity.supported_codecs

    def test_supported_sample_rates(self, mock_stt_entity):
        """Test supported_sample_rates returns correct sample rates."""
        assert (
            stt.AudioSampleRates.SAMPLERATE_16000
            in mock_stt_entity.supported_sample_rates
        )
        assert (
            stt.AudioSampleRates.SAMPLERATE_32000
            in mock_stt_entity.supported_sample_rates
        )

    def test_supported_channels(self, mock_stt_entity):
        """Test supported_channels returns correct channels."""
        assert stt.AudioChannels.CHANNEL_MONO in mock_stt_entity.supported_channels

    @pytest.mark.asyncio
    async def test_async_process_audio_stream_success(self, mock_stt_entity, hass):
        """Test async_process_audio_stream returns successful transcription."""
        metadata = stt.SpeechMetadata(
            language="en-US",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )

        audio_stream = await async_gen(b"fake_audio_data")

        with patch.object(
            mock_stt_entity._client,  # noqa: SLF001
            "async_stt",
            new_callable=AsyncMock,
            return_value=STT_RESPONSE_TEXT,
        ):
            result = await mock_stt_entity.async_process_audio_stream(
                metadata, audio_stream
            )

        assert result.text == STT_RESPONSE_TEXT
        assert result.result == stt.SpeechResultState.SUCCESS

    @pytest.mark.asyncio
    async def test_async_process_audio_stream_empty_result(self, mock_stt_entity, hass):
        """Test async_process_audio_stream handles empty transcription."""
        metadata = stt.SpeechMetadata(
            language="en-US",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )

        audio_stream = await async_gen(b"fake_audio_data")

        with patch.object(
            mock_stt_entity._client,  # noqa: SLF001
            "async_stt",
            new_callable=AsyncMock,
            return_value="",
        ):
            result = await mock_stt_entity.async_process_audio_stream(
                metadata, audio_stream
            )

        assert result.text is None
        assert result.result == stt.SpeechResultState.ERROR

    @pytest.mark.asyncio
    async def test_async_process_audio_stream_error(self, mock_stt_entity, hass):
        """Test async_process_audio_stream handles errors gracefully."""
        metadata = stt.SpeechMetadata(
            language="en-US",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )

        audio_stream = await async_gen(b"fake_audio_data")

        with patch.object(
            mock_stt_entity._client,  # noqa: SLF001
            "async_stt",
            new_callable=AsyncMock,
            side_effect=Exception("STT API Error"),
        ):
            result = await mock_stt_entity.async_process_audio_stream(
                metadata, audio_stream
            )

        assert result.text is None
        assert result.result == stt.SpeechResultState.ERROR


class TestSTTSetup:
    """Test STT platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_entity(
        self, hass: HomeAssistant, mock_server_response
    ):
        """Test async_setup_entry creates STT entity."""
        from custom_components.minimax.stt import async_setup_entry  # noqa: PLC0415

        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "stt_subentry_001"
        subentry.subentry_type = "stt"
        subentry.title = "MiniMax STT"
        subentry.data = RECOMMENDED_STT_OPTIONS.copy()
        config_entry.subentries = {"stt": subentry}

        mock_client = create_mock_minimax_client()
        config_entry.runtime_data = mock_client

        entities_added = []

        def mock_add_entities(entities, config_subentry_id=None):
            entities_added.extend(entities)

        with patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ):
            await async_setup_entry(hass, config_entry, mock_add_entities)
            await hass.async_block_till_done()

        assert len(entities_added) == 1
        assert entities_added[0]._attr_name == "MiniMax STT"  # noqa: SLF001


async def async_gen(data: bytes):
    """Helper to create an async generator."""

    async def generator():
        for chunk in [data[i : i + 1024] for i in range(0, len(data), 1024)]:
            yield chunk

    return generator()

"""Tests for MiniMax TTS entity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.minimax import tts as minimax_tts
from custom_components.minimax.const import (
    CONF_PITCH,
    CONF_SPEED,
    CONF_VOICE_ID,
    CONF_VOL,
    RECOMMENDED_TTS_OPTIONS,
    VOICE_IDS,
)
from homeassistant.components.tts import ATTR_VOICE
from homeassistant.core import HomeAssistant
from tests import (  # noqa: TID251
    TTS_RESPONSE_BYTES,
    create_mock_minimax_client,
    create_mock_minimax_config_entry,
)

pytest_plugins = "pytest_homeassistant_custom_component"


class TestMiniMaxTTSEntity:
    """Test MiniMaxTTSEntity."""

    @pytest.fixture
    def mock_config_entry_with_tts_subentry(self, hass: HomeAssistant):
        """Create a config entry with a TTS subentry."""
        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "tts_subentry_001"
        subentry.subentry_type = "tts"
        subentry.title = "MiniMax TTS"
        subentry.data = RECOMMENDED_TTS_OPTIONS.copy()
        config_entry.subentries = {"tts": subentry}
        return config_entry

    @pytest.fixture
    def mock_tts_entity(self, mock_config_entry_with_tts_subentry, hass: HomeAssistant):
        """Create a TTS entity for testing."""
        mock_client = create_mock_minimax_client()
        entity = minimax_tts.MiniMaxTTSEntity(
            config_entry=mock_config_entry_with_tts_subentry,
            subentry=mock_config_entry_with_tts_subentry.subentries["tts"],
            client=mock_client,
        )
        entity.hass = hass
        return entity

    def test_entity_properties(self, mock_tts_entity):
        """Test entity properties are set correctly."""
        assert mock_tts_entity._attr_name == "MiniMax TTS"  # noqa: SLF001
        assert mock_tts_entity._attr_unique_id == "tts_subentry_001"  # noqa: SLF001
        assert mock_tts_entity._attr_default_language == "en-US"  # noqa: SLF001

    def test_supported_options(self, mock_tts_entity):
        """Test supported_options returns correct options."""
        assert ATTR_VOICE in mock_tts_entity.supported_options

    def test_supported_languages(self, mock_tts_entity):
        """Test supported_languages returns correct languages."""
        assert "en-US" in mock_tts_entity.supported_languages
        assert "zh-CN" in mock_tts_entity.supported_languages

    def test_supported_voices(self, mock_tts_entity):
        """Test supported_voices returns voice list for en-US."""
        voices = mock_tts_entity.async_get_supported_voices("en-US")
        assert len(voices) > 0
        voice_ids = [v.voice_id for v in voices]
        for voice_id in VOICE_IDS.get("en-US", []):
            assert voice_id in voice_ids

    def test_supported_voices_for_unsupported_language(self, mock_tts_entity):
        """Test supported_voices returns None for unsupported language."""
        voices = mock_tts_entity.async_get_supported_voices("fr-FR")
        assert voices is None

    def test_default_options(self, mock_tts_entity):
        """Test default_options returns correct options."""
        options = mock_tts_entity.default_options
        assert ATTR_VOICE in options
        assert options[ATTR_VOICE] == RECOMMENDED_TTS_OPTIONS[CONF_VOICE_ID]

    @pytest.mark.asyncio
    async def test_async_get_tts_audio_success(self, mock_tts_entity, hass):
        """Test async_get_tts_audio returns successful audio."""
        with patch.object(
            mock_tts_entity._client,  # noqa: SLF001
            "async_tts",
            new_callable=AsyncMock,
            return_value=TTS_RESPONSE_BYTES,
        ):
            result = await mock_tts_entity.async_get_tts_audio(
                message="Hello world",
                language="en-US",
                options={ATTR_VOICE: "English_PlayfulGirl"},
            )

        assert result[0] == "mp3"
        assert result[1] == TTS_RESPONSE_BYTES

    @pytest.mark.asyncio
    async def test_async_get_tts_audio_with_custom_options(self, mock_tts_entity, hass):
        """Test async_get_tts_audio uses custom options."""
        custom_options = {
            ATTR_VOICE: "English_Narrator",
            CONF_SPEED: 1.5,
            CONF_VOL: 0.8,
            CONF_PITCH: 2,
        }

        with patch.object(
            mock_tts_entity._client,  # noqa: SLF001
            "async_tts",
            new_callable=AsyncMock,
            return_value=TTS_RESPONSE_BYTES,
        ) as mock_tts:
            await mock_tts_entity.async_get_tts_audio(
                message="Hello world",
                language="en-US",
                options=custom_options,
            )

            mock_tts.assert_called_once()
            call_kwargs = mock_tts.call_args[1]
            assert call_kwargs["voice_id"] == "English_Narrator"
            assert call_kwargs["speed"] == 1.5
            assert call_kwargs["vol"] == 0.8
            assert call_kwargs["pitch"] == 2

    @pytest.mark.asyncio
    async def test_async_get_tts_audio_error(self, mock_tts_entity, hass):
        """Test async_get_tts_audio handles errors gracefully."""
        with patch.object(
            mock_tts_entity._client,  # noqa: SLF001
            "async_tts",
            new_callable=AsyncMock,
            side_effect=Exception("TTS API Error"),
        ):
            result = await mock_tts_entity.async_get_tts_audio(
                message="Hello world",
                language="en-US",
                options={ATTR_VOICE: "English_PlayfulGirl"},
            )

        assert result[0] is None
        assert result[1] is None

    @pytest.mark.asyncio
    async def test_async_get_tts_audio_uses_subentry_defaults(
        self, mock_tts_entity, hass
    ):
        """Test async_get_tts_audio uses subentry default options."""
        with patch.object(
            mock_tts_entity._client,  # noqa: SLF001
            "async_tts",
            new_callable=AsyncMock,
            return_value=TTS_RESPONSE_BYTES,
        ) as mock_tts:
            await mock_tts_entity.async_get_tts_audio(
                message="Hello world",
                language="en-US",
                options={},
            )

            mock_tts.assert_called_once()
            call_kwargs = mock_tts.call_args[1]
            assert call_kwargs["voice_id"] == RECOMMENDED_TTS_OPTIONS[CONF_VOICE_ID]
            assert call_kwargs["speed"] == RECOMMENDED_TTS_OPTIONS[CONF_SPEED]
            assert call_kwargs["vol"] == RECOMMENDED_TTS_OPTIONS[CONF_VOL]
            assert call_kwargs["pitch"] == RECOMMENDED_TTS_OPTIONS[CONF_PITCH]


class TestTTSSetup:
    """Test TTS platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_entity(
        self, hass: HomeAssistant, mock_server_response
    ):
        """Test async_setup_entry creates TTS entity."""
        from custom_components.minimax.tts import async_setup_entry  # noqa: PLC0415

        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "tts_subentry_001"
        subentry.subentry_type = "tts"
        subentry.title = "MiniMax TTS"
        subentry.data = RECOMMENDED_TTS_OPTIONS.copy()
        config_entry.subentries = {"tts": subentry}

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
        assert entities_added[0]._attr_name == "MiniMax TTS"  # noqa: SLF001

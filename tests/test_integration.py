"""Integration-level tests for MiniMax integration.

These tests verify that entities properly register with Home Assistant
and respond correctly to state queries and changes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.minimax import (
    async_setup_entry,
    async_unload_entry,
    conversation as minimax_conversation,
)
from custom_components.minimax.const import RECOMMENDED_CONVERSATION_OPTIONS
from custom_components.minimax.conversation import MiniMaxConversationEntity
from custom_components.minimax.stt import MiniMaxSTTEntity
from custom_components.minimax.tts import MiniMaxTTSEntity
from homeassistant.components import conversation, stt
from homeassistant.components.conversation.models import ConversationInput
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant
from tests import (  # noqa: TID251
    CHAT_RESPONSE_SUCCESS,
    STT_RESPONSE_TEXT,
    TTS_RESPONSE_BYTES,
    create_mock_minimax_client,
    create_mock_minimax_config_entry,
)

pytest_plugins = "pytest_homeassistant_custom_component"


class TestConversationEntityRegistration:
    """Test conversation entity registration with Home Assistant."""

    @pytest.fixture
    def config_entry_with_conversation_subentry(self, hass: HomeAssistant):
        """Create a config entry with a conversation subentry."""
        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "conv_subentry_001"
        subentry.subentry_type = "conversation"
        subentry.title = "MiniMax Conversation"
        subentry.data = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        config_entry.subentries = {"conversation": subentry}
        return config_entry

    @pytest.mark.asyncio
    async def test_conversation_entity_registered_with_agent_manager(
        self,
        hass: HomeAssistant,
        config_entry_with_conversation_subentry: ConfigEntry,
    ):
        """Test conversation entity is registered with HA agent manager."""
        mock_client = create_mock_minimax_client()
        config_entry_with_conversation_subentry.runtime_data = mock_client

        entity = MiniMaxConversationEntity(
            entry=config_entry_with_conversation_subentry,
            subentry=config_entry_with_conversation_subentry.subentries["conversation"],
            client=mock_client,
        )

        entity.hass = hass

        with patch.object(
            conversation,
            "async_set_agent",
            new_callable=AsyncMock,
        ) as mock_set_agent:
            await entity.async_added_to_hass()
            await hass.async_block_till_done()

            mock_set_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_entity_unregistered_on_remove(
        self,
        hass: HomeAssistant,
        config_entry_with_conversation_subentry: ConfigEntry,
    ):
        """Test conversation entity is unregistered when removed from HA."""
        mock_client = create_mock_minimax_client()
        config_entry_with_conversation_subentry.runtime_data = mock_client

        entity = MiniMaxConversationEntity(
            entry=config_entry_with_conversation_subentry,
            subentry=config_entry_with_conversation_subentry.subentries["conversation"],
            client=mock_client,
        )

        entity.hass = hass

        with (
            patch.object(
                conversation,
                "async_set_agent",
                new_callable=AsyncMock,
            ) as mock_set_agent,
            patch.object(
                conversation,
                "async_unset_agent",
                new_callable=AsyncMock,
            ) as mock_unset_agent,
        ):
            await entity.async_added_to_hass()
            await hass.async_block_till_done()

            await entity.async_will_remove_from_hass()
            await hass.async_block_till_done()

            mock_set_agent.assert_called_once()
            mock_unset_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_entity_process_returns_intent_response(
        self,
        hass: HomeAssistant,
        config_entry_with_conversation_subentry: ConfigEntry,
    ):
        """Test conversation entity returns proper IntentResponse."""
        mock_client = create_mock_minimax_client()
        mock_client.async_chat = AsyncMock(return_value=CHAT_RESPONSE_SUCCESS.copy())
        config_entry_with_conversation_subentry.runtime_data = mock_client

        entity = MiniMaxConversationEntity(
            entry=config_entry_with_conversation_subentry,
            subentry=config_entry_with_conversation_subentry.subentries["conversation"],
            client=mock_client,
        )

        entity.hass = hass

        user_input = ConversationInput(
            text="Hello",
            context=Context(user_id=None),
            conversation_id=None,
            device_id=None,
            satellite_id=None,
            language="en-US",
            agent_id=None,
        )

        with (
            patch.object(
                minimax_conversation,
                "_get_homeassistant_tools",
                return_value=[],
            ),
            patch.object(
                minimax_conversation,
                "_build_system_prompt",
                return_value="You are a helpful assistant.",
            ),
        ):
            result = await entity.async_process(user_input)

        assert result is not None
        assert hasattr(result, "response")
        assert result.response.speech is not None


class TestTTSEntityRegistration:
    """Test TTS entity registration with Home Assistant."""

    @pytest.fixture
    def config_entry_with_tts_subentry(self, hass: HomeAssistant):
        """Create a config entry with a TTS subentry."""
        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "tts_subentry_001"
        subentry.subentry_type = "tts"
        subentry.title = "MiniMax TTS"
        subentry.data = {
            "language": "en-US",
            "voice_id": "English_PlayfulGirl",
            "speed": 1.0,
            "vol": 1.0,
            "pitch": 1.0,
        }
        config_entry.subentries = {"tts": subentry}
        return config_entry

    @pytest.mark.asyncio
    async def test_tts_entity_creates_with_correct_properties(
        self,
        hass: HomeAssistant,
        config_entry_with_tts_subentry: ConfigEntry,
    ):
        """Test TTS entity is created with correct properties."""
        mock_client = create_mock_minimax_client()
        config_entry_with_tts_subentry.runtime_data = mock_client

        entity = MiniMaxTTSEntity(
            config_entry=config_entry_with_tts_subentry,
            subentry=config_entry_with_tts_subentry.subentries["tts"],
            client=mock_client,
        )

        entity.hass = hass

        assert entity._attr_name == "MiniMax TTS"  # noqa: SLF001
        assert entity._attr_unique_id == "tts_subentry_001"  # noqa: SLF001
        assert entity._attr_default_language == "en-US"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_tts_entity_generates_audio(
        self,
        hass: HomeAssistant,
        config_entry_with_tts_subentry: ConfigEntry,
    ):
        """Test TTS entity generates audio correctly."""
        mock_client = create_mock_minimax_client()
        mock_client.async_tts = AsyncMock(return_value=TTS_RESPONSE_BYTES)
        config_entry_with_tts_subentry.runtime_data = mock_client

        entity = MiniMaxTTSEntity(
            config_entry=config_entry_with_tts_subentry,
            subentry=config_entry_with_tts_subentry.subentries["tts"],
            client=mock_client,
        )

        entity.hass = hass

        result = await entity.async_get_tts_audio(
            message="Hello world",
            language="en-US",
            options={},
        )

        assert result is not None
        assert result[0] == "mp3"
        assert result[1] == TTS_RESPONSE_BYTES


class TestSTTEntityRegistration:
    """Test STT entity registration with Home Assistant."""

    @pytest.fixture
    def config_entry_with_stt_subentry(self, hass: HomeAssistant):
        """Create a config entry with an STT subentry."""
        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "stt_subentry_001"
        subentry.subentry_type = "stt"
        subentry.title = "MiniMax STT"
        subentry.data = {
            "language": "en-US",
            "prompt": "Transcribe this audio.",
        }
        config_entry.subentries = {"stt": subentry}
        return config_entry

    @pytest.mark.asyncio
    async def test_stt_entity_creates_with_correct_properties(
        self,
        hass: HomeAssistant,
        config_entry_with_stt_subentry: ConfigEntry,
    ):
        """Test STT entity is created with correct properties."""
        mock_client = create_mock_minimax_client()
        config_entry_with_stt_subentry.runtime_data = mock_client

        entity = MiniMaxSTTEntity(
            config_entry=config_entry_with_stt_subentry,
            subentry=config_entry_with_stt_subentry.subentries["stt"],
            client=mock_client,
        )

        entity.hass = hass

        assert entity._attr_name == "MiniMax STT"  # noqa: SLF001
        assert entity._attr_unique_id == "stt_subentry_001"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_stt_entity_processes_audio_stream(
        self,
        hass: HomeAssistant,
        config_entry_with_stt_subentry: ConfigEntry,
    ):
        """Test STT entity processes audio stream correctly."""
        mock_client = create_mock_minimax_client()
        mock_client.async_stt = AsyncMock(return_value=STT_RESPONSE_TEXT)
        config_entry_with_stt_subentry.runtime_data = mock_client

        entity = MiniMaxSTTEntity(
            config_entry=config_entry_with_stt_subentry,
            subentry=config_entry_with_stt_subentry.subentries["stt"],
            client=mock_client,
        )

        entity.hass = hass

        metadata = stt.SpeechMetadata(
            language="en-US",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )

        async def async_gen():
            yield b"fake_audio_data"

        result = await entity.async_process_audio_stream(metadata, async_gen())

        assert result is not None
        assert result.text == STT_RESPONSE_TEXT
        assert result.result == stt.SpeechResultState.SUCCESS


class TestIntegrationSetupFlow:
    """Test full integration setup flow."""

    @pytest.mark.asyncio
    async def test_full_setup_registers_all_entities(self, hass: HomeAssistant):
        """Test full setup registers conversation, TTS, and STT entities."""
        from custom_components.minimax.conversation import (  # noqa: PLC0415, I001
            async_setup_entry as conv_setup,
        )
        from custom_components.minimax.stt import async_setup_entry as stt_setup  # noqa: PLC0415
        from custom_components.minimax.tts import async_setup_entry as tts_setup  # noqa: PLC0415

        config_entry = create_mock_minimax_config_entry(hass)

        conv_subentry = MagicMock()
        conv_subentry.subentry_id = "conv_001"
        conv_subentry.subentry_type = "conversation"
        conv_subentry.title = "MiniMax Conversation"
        conv_subentry.data = {"language": "en-US"}

        tts_subentry = MagicMock()
        tts_subentry.subentry_id = "tts_001"
        tts_subentry.subentry_type = "tts"
        tts_subentry.title = "MiniMax TTS"
        tts_subentry.data = {
            "language": "en-US",
            "voice_id": "English_PlayfulGirl",
            "speed": 1.0,
            "vol": 1.0,
            "pitch": 1.0,
        }

        stt_subentry = MagicMock()
        stt_subentry.subentry_id = "stt_001"
        stt_subentry.subentry_type = "stt"
        stt_subentry.title = "MiniMax STT"
        stt_subentry.data = {"language": "en-US", "prompt": "Transcribe."}

        config_entry.subentries = {
            "conversation": conv_subentry,
            "tts": tts_subentry,
            "stt": stt_subentry,
        }

        mock_client = create_mock_minimax_client()
        config_entry.runtime_data = mock_client

        conv_entities_added = []
        tts_entities_added = []
        stt_entities_added = []

        def mock_conv_add_entities(entities, config_subentry_id=None):
            conv_entities_added.extend(entities)

        def mock_tts_add_entities(entities, config_subentry_id=None):
            tts_entities_added.extend(entities)

        def mock_stt_add_entities(entities, config_subentry_id=None):
            stt_entities_added.extend(entities)

        with patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ):
            await conv_setup(hass, config_entry, mock_conv_add_entities)
            await tts_setup(hass, config_entry, mock_tts_add_entities)
            await stt_setup(hass, config_entry, mock_stt_add_entities)
            await hass.async_block_till_done()

        assert len(conv_entities_added) == 1
        assert len(tts_entities_added) == 1
        assert len(stt_entities_added) == 1

        assert conv_entities_added[0]._attr_name == "MiniMax Conversation"  # noqa: SLF001
        assert tts_entities_added[0]._attr_name == "MiniMax TTS"  # noqa: SLF001
        assert stt_entities_added[0]._attr_name == "MiniMax STT"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_integration_unload_removes_entities(self, hass: HomeAssistant):
        """Test unloading integration removes entities properly."""
        config_entry = create_mock_minimax_config_entry(hass)
        mock_client = create_mock_minimax_client()

        with (
            patch(
                "custom_components.minimax.MiniMaxApiClient",
                return_value=mock_client,
            ),
            patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=True
            ),
        ):
            result = await async_setup_entry(hass, config_entry)
            assert result is True

        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            unload_result = await async_unload_entry(hass, config_entry)
            assert unload_result is True


class TestEntityProperties:
    """Test entity properties and configuration."""

    @pytest.mark.asyncio
    async def test_conversation_entity_has_correct_supported_features(
        self, hass: HomeAssistant
    ):
        """Test conversation entity has correct supported features."""
        from custom_components.minimax.conversation import (  # noqa: PLC0415
            MiniMaxConversationEntity,
            conversation,
        )

        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "conv_001"
        subentry.subentry_type = "conversation"
        subentry.title = "MiniMax"
        subentry.data = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        config_entry.subentries = {"conversation": subentry}

        mock_client = create_mock_minimax_client()
        config_entry.runtime_data = mock_client

        entity = MiniMaxConversationEntity(
            entry=config_entry,
            subentry=subentry,
            client=mock_client,
        )

        assert (
            conversation.ConversationEntityFeature.CONTROL in entity.supported_features
        )

    @pytest.mark.asyncio
    async def test_tts_entity_supports_correct_languages_and_voices(
        self, hass: HomeAssistant
    ):
        """Test TTS entity supports correct languages and voices."""

        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "tts_001"
        subentry.subentry_type = "tts"
        subentry.title = "MiniMax TTS"
        subentry.data = {
            "language": "en-US",
            "voice_id": "English_PlayfulGirl",
            "speed": 1.0,
            "vol": 1.0,
            "pitch": 1.0,
        }
        config_entry.subentries = {"tts": subentry}

        mock_client = create_mock_minimax_client()
        config_entry.runtime_data = mock_client

        entity = MiniMaxTTSEntity(
            config_entry=config_entry,
            subentry=subentry,
            client=mock_client,
        )

        assert "en-US" in entity.supported_languages
        assert "zh-CN" in entity.supported_languages

        en_us_voices = entity.async_get_supported_voices("en-US")
        assert en_us_voices is not None
        assert len(en_us_voices) > 0

    @pytest.mark.asyncio
    async def test_stt_entity_supports_correct_languages(self, hass: HomeAssistant):
        """Test STT entity supports correct languages."""
        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "stt_001"
        subentry.subentry_type = "stt"
        subentry.title = "MiniMax STT"
        subentry.data = {"language": "en-US", "prompt": "Transcribe."}
        config_entry.subentries = {"stt": subentry}

        mock_client = create_mock_minimax_client()
        config_entry.runtime_data = mock_client

        entity = MiniMaxSTTEntity(
            config_entry=config_entry,
            subentry=subentry,
            client=mock_client,
        )

        assert "en-US" in entity.supported_languages
        assert "zh-CN" in entity.supported_languages


class TestConfigEntryState:
    """Test ConfigEntry state management."""

    @pytest.mark.asyncio
    async def test_config_entry_runtime_data_set_after_setup(self, hass: HomeAssistant):
        """Test ConfigEntry runtime_data is set correctly after setup."""
        config_entry = create_mock_minimax_config_entry(hass)
        mock_client = create_mock_minimax_client()

        with (
            patch(
                "custom_components.minimax.MiniMaxApiClient",
                return_value=mock_client,
            ),
            patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=True
            ),
        ):
            result = await async_setup_entry(hass, config_entry)
            await hass.async_block_till_done()

        assert result is True
        assert hasattr(config_entry, "runtime_data")
        assert config_entry.runtime_data is mock_client

"""Tests for MiniMax config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.minimax.config_flow import (
    CONF_API_KEY,
    CONF_CHAT_MODEL,
    CONF_CONVERSATION_EXPIRY_MINUTES,
    CONF_CONVERSATION_MAX_TOKENS,
    CONF_CONVERSATION_TTS_ENABLED,
    CONF_MEMORY_ENABLED,
    CONF_PITCH,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_SPEED,
    CONF_VOICE_ID,
    CONF_VOL,
    LLMSubentryFlowHandler,
    MiniMaxConfigFlow,
    async_minimax_option_schema,
)
from custom_components.minimax.const import (
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TTS_OPTIONS,
)
from homeassistant.data_entry_flow import FlowResultType


class TestMiniMaxConfigFlow:
    """Test MiniMaxConfigFlow."""

    @pytest.fixture
    def flow(self, hass):
        """Create a MiniMaxConfigFlow instance."""
        flow = MiniMaxConfigFlow()
        flow.hass = hass
        flow.context = {"source": "user"}
        flow.handler = "minimax"
        return flow

    async def test_user_flow_shows_form(self, flow):
        """Test user flow shows form on first step."""
        result = await flow.async_step_user(user_input=None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert CONF_API_KEY in str(result["data_schema"])

    async def test_user_flow_success(self, flow, hass):
        """Test successful user config flow creates entry."""
        with (
            patch(
                "custom_components.minimax.config_flow.MiniMaxApiClient"
            ) as mock_client,
            patch(
                "custom_components.minimax.config_flow.async_get_clientsession"
            ) as mock_session,
        ):
            instance = AsyncMock()
            instance.async_verify_connection = AsyncMock(return_value=True)
            mock_client.return_value = instance
            mock_session.return_value = MagicMock()

            result = await flow.async_step_user(
                user_input={CONF_API_KEY: "valid_key_123"}
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "MiniMax"
        assert result["data"][CONF_API_KEY] == "valid_key_123"
        assert len(result["subentries"]) == 4

    async def test_user_flow_invalid_auth(self, flow, hass):
        """Test user config flow with auth failure."""
        from custom_components.minimax.api import MiniMaxApiClientError

        with (
            patch(
                "custom_components.minimax.config_flow.MiniMaxApiClient"
            ) as mock_client,
            patch(
                "custom_components.minimax.config_flow.async_get_clientsession"
            ) as mock_session,
        ):
            instance = AsyncMock()
            instance.async_verify_connection = AsyncMock(
                side_effect=MiniMaxApiClientError("Invalid API key")
            )
            mock_client.return_value = instance
            mock_session.return_value = MagicMock()

            result = await flow.async_step_user(
                user_input={CONF_API_KEY: "invalid_key"}
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_user_flow_cannot_connect(self, flow, hass):
        """Test user config flow with connection error."""
        from custom_components.minimax.api import MiniMaxApiClientError

        with (
            patch(
                "custom_components.minimax.config_flow.MiniMaxApiClient"
            ) as mock_client,
            patch(
                "custom_components.minimax.config_flow.async_get_clientsession"
            ) as mock_session,
        ):
            instance = AsyncMock()
            instance.async_verify_connection = AsyncMock(
                side_effect=MiniMaxApiClientError("Connection refused")
            )
            mock_client.return_value = instance
            mock_session.return_value = MagicMock()

            result = await flow.async_step_user(user_input={CONF_API_KEY: "test_key"})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_user_flow_duplicate_entry_aborts(self, flow, hass):
        """Test duplicate entries are aborted."""
        from homeassistant.data_entry_flow import AbortFlow
        from tests import TEST_API_KEY, create_mock_minimax_config_entry

        create_mock_minimax_config_entry(hass)

        with pytest.raises(AbortFlow) as exc_info:
            await flow.async_step_user(user_input={CONF_API_KEY: TEST_API_KEY})

        assert exc_info.value.reason == "already_configured"

    async def test_reauth_flow(self, hass):
        """Test reauthentication flow."""
        from homeassistant.config_entries import SOURCE_REAUTH

        flow = MiniMaxConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_REAUTH}

        result = await flow.async_step_reauth(entry_data={})

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

    def test_async_get_supported_subentry_types(self):
        """Test supported subentry types are returned."""
        types = MiniMaxConfigFlow.async_get_supported_subentry_types(None)
        assert "conversation" in types
        assert "tts" in types
        assert "stt" in types
        assert "ai_task_data" in types


class TestAsyncMinimaxOptionSchema:
    """Test async_minimax_option_schema function."""

    def test_conversation_schema_includes_all_fields(self):
        """Test conversation schema contains expected fields."""
        schema_dict = async_minimax_option_schema(
            is_new=True,
            subentry_type="conversation",
            options=RECOMMENDED_CONVERSATION_OPTIONS,
        )
        schema = vol.Schema(schema_dict)

        keys = list(schema.schema.keys())
        key_names = [
            k.schema for k in keys if isinstance(k, (vol.Optional, vol.Required))
        ]

        assert "name" in key_names
        assert CONF_CHAT_MODEL in key_names
        assert CONF_PROMPT in key_names
        assert CONF_CONVERSATION_TTS_ENABLED in key_names
        assert CONF_CONVERSATION_MAX_TOKENS in key_names
        assert CONF_CONVERSATION_EXPIRY_MINUTES in key_names
        assert CONF_MEMORY_ENABLED in key_names

    def test_tts_schema_includes_all_fields(self):
        """Test TTS schema contains expected fields."""
        schema_dict = async_minimax_option_schema(
            is_new=True,
            subentry_type="tts",
            options=RECOMMENDED_TTS_OPTIONS,
        )
        schema = vol.Schema(schema_dict)

        keys = list(schema.schema.keys())
        key_names = [
            k.schema for k in keys if isinstance(k, (vol.Optional, vol.Required))
        ]

        assert "name" in key_names
        assert CONF_VOICE_ID in key_names
        assert CONF_SPEED in key_names
        assert CONF_VOL in key_names
        assert CONF_PITCH in key_names

    def test_stt_schema_includes_all_fields(self):
        """Test STT schema contains expected fields."""
        schema_dict = async_minimax_option_schema(
            is_new=True,
            subentry_type="stt",
            options=RECOMMENDED_STT_OPTIONS,
        )
        schema = vol.Schema(schema_dict)

        keys = list(schema.schema.keys())
        key_names = [
            k.schema for k in keys if isinstance(k, (vol.Optional, vol.Required))
        ]

        assert "name" in key_names
        assert CONF_PROMPT in key_names

    def test_reconfigure_has_no_name(self):
        """Test reconfigure schema does not include the name field."""
        schema_dict = async_minimax_option_schema(
            is_new=False,
            subentry_type="conversation",
            options=RECOMMENDED_CONVERSATION_OPTIONS,
        )
        schema = vol.Schema(schema_dict)

        keys = list(schema.schema.keys())
        key_names = [
            k.schema for k in keys if isinstance(k, (vol.Optional, vol.Required))
        ]

        assert "name" not in key_names

    def test_all_schemas_include_recommended(self):
        """Test all schemas include the recommended checkbox."""
        for subentry_type in ("conversation", "tts", "stt"):
            schema_dict = async_minimax_option_schema(
                is_new=True,
                subentry_type=subentry_type,
                options={},
            )
            schema = vol.Schema(schema_dict)

            keys = list(schema.schema.keys())
            key_names = [k.schema for k in keys if isinstance(k, vol.Required)]

            assert CONF_RECOMMENDED in key_names


class TestLLMSubentryFlowHandler:
    """Test LLMSubentryFlowHandler."""

    @pytest.fixture
    def flow(self, hass):
        """Create a LLMSubentryFlowHandler instance."""
        from tests import create_mock_minimax_config_entry

        entry = create_mock_minimax_config_entry(hass)

        flow = LLMSubentryFlowHandler()
        flow.hass = hass
        flow.handler = ("minimax", "conversation")
        flow.context = {"source": "user", "entry_id": entry.entry_id}
        return flow

    async def test_subentry_flow_shows_form(self, flow):
        """Test subentry flow shows form on first step."""
        result = await flow.async_step_user(user_input=None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "set_options"

    async def test_conversation_schema(self, flow):
        """Test conversation subentry schema has expected fields."""
        result = await flow.async_step_user(user_input=None)
        schema_text = str(result["data_schema"])

        assert CONF_CHAT_MODEL in schema_text
        assert CONF_PROMPT in schema_text
        assert CONF_CONVERSATION_TTS_ENABLED in schema_text

    async def test_tts_schema(self, hass):
        """Test TTS subentry schema has expected fields."""
        from tests import create_mock_minimax_config_entry

        entry = create_mock_minimax_config_entry(hass)

        flow = LLMSubentryFlowHandler()
        flow.hass = hass
        flow.handler = ("minimax", "tts")
        flow.context = {"source": "user", "entry_id": entry.entry_id}

        result = await flow.async_step_user(user_input=None)

        assert result["type"] == FlowResultType.FORM
        schema_text = str(result["data_schema"])
        assert CONF_VOICE_ID in schema_text
        assert CONF_SPEED in schema_text

    async def test_stt_schema(self, hass):
        """Test STT subentry schema has expected fields."""
        from tests import create_mock_minimax_config_entry

        entry = create_mock_minimax_config_entry(hass)

        flow = LLMSubentryFlowHandler()
        flow.hass = hass
        flow.handler = ("minimax", "stt")
        flow.context = {"source": "user", "entry_id": entry.entry_id}

        result = await flow.async_step_user(user_input=None)

        assert result["type"] == FlowResultType.FORM
        schema_text = str(result["data_schema"])
        assert CONF_PROMPT in schema_text

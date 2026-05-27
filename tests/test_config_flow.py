"""Tests for MiniMax config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.minimax import config_flow
from custom_components.minimax.api import MiniMaxApiClientError
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytest_plugins = "pytest_homeassistant_custom_component"


class TestMiniMaxConfigFlow:
    """Test MiniMaxConfigFlow."""

    @pytest.fixture
    def mock_client_verify_success(self):
        """Mock successful connection verification."""
        with patch(
            "custom_components.minimax.config_flow.MiniMaxApiClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_instance.async_verify_connection = AsyncMock(return_value=True)
            mock_client.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def mock_client_verify_auth_failure(self):
        """Mock auth failure during connection verification."""
        with patch(
            "custom_components.minimax.config_flow.MiniMaxApiClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_instance.async_verify_connection = AsyncMock(
                side_effect=MiniMaxApiClientError("Invalid API key")
            )
            mock_client.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def mock_client_verify_connection_error(self):
        """Mock connection error during verification."""
        with patch(
            "custom_components.minimax.config_flow.MiniMaxApiClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_instance.async_verify_connection = AsyncMock(
                side_effect=MiniMaxApiClientError("Connection failed")
            )
            mock_client.return_value = mock_instance
            yield mock_instance

    async def test_user_flow_success(
        self,
        hass: HomeAssistant,
        mock_client_verify_success,
    ):
        """Test successful user config flow."""
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "user"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"api_key": "valid_api_key_123"},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "MiniMax"
        assert result["data"]["api_key"] == "valid_api_key_123"

    async def test_user_flow_auth_failure(
        self,
        hass: HomeAssistant,
        mock_client_verify_auth_failure,
    ):
        """Test user config flow with auth failure."""
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "user"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"api_key": "invalid_api_key"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_user_flow_connection_error(
        self,
        hass: HomeAssistant,
        mock_client_verify_connection_error,
    ):
        """Test user config flow with connection error."""
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "user"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"api_key": "test_api_key"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


class TestMiniMaxSubentryFlow:
    """Test LLMSubentryFlowHandler for subentries."""

    async def test_subentry_flow_conversation(self, hass: HomeAssistant):
        """Test subentry flow for conversation."""
        flow = config_flow.LLMSubentryFlowHandler()
        flow.hass = hass
        flow.handler = (config_flow.DOMAIN, "conversation")
        flow.context = {"source": "user"}

        result = await flow.async_step_user(user_input={})

        assert result["type"] == FlowResultType.FORM

    async def test_subentry_flow_tts(self, hass: HomeAssistant):
        """Test subentry flow for TTS."""
        flow = config_flow.LLMSubentryFlowHandler()
        flow.hass = hass
        flow.handler = (config_flow.DOMAIN, "tts")
        flow.context = {"source": "user"}

        result = await flow.async_step_user(user_input={})

        assert result["type"] == FlowResultType.FORM

    async def test_subentry_flow_stt(self, hass: HomeAssistant):
        """Test subentry flow for STT."""
        flow = config_flow.LLMSubentryFlowHandler()
        flow.hass = hass
        flow.handler = (config_flow.DOMAIN, "stt")
        flow.context = {"source": "user"}

        result = await flow.async_step_user(user_input={})

        assert result["type"] == FlowResultType.FORM

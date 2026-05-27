"""Tests for MiniMax conversation entity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.minimax import conversation as minimax_conversation
from custom_components.minimax.const import RECOMMENDED_CONVERSATION_OPTIONS
from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL
from homeassistant.core import Context, HomeAssistant
from tests import (  # noqa: TID251
    CHAT_RESPONSE_SUCCESS,
    create_mock_minimax_client,
    create_mock_minimax_config_entry,
)

pytest_plugins = "pytest_homeassistant_custom_component"


class TestMiniMaxConversationEntity:
    """Test MiniMaxConversationEntity."""

    @pytest.fixture
    def mock_config_entry_with_conversation_subentry(self, hass: HomeAssistant):
        """Create a config entry with a conversation subentry."""
        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "conversation_subentry_001"
        subentry.subentry_type = "conversation"
        subentry.title = "MiniMax Conversation"
        subentry.data = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        config_entry.subentries = {"conversation": subentry}
        return config_entry

    @pytest.fixture
    def mock_conversation_entity(
        self, mock_config_entry_with_conversation_subentry, hass: HomeAssistant
    ):
        """Create a conversation entity for testing."""
        mock_client = create_mock_minimax_client()
        entity = minimax_conversation.MiniMaxConversationEntity(
            entry=mock_config_entry_with_conversation_subentry,
            subentry=mock_config_entry_with_conversation_subentry.subentries[
                "conversation"
            ],
            client=mock_client,
        )
        entity.hass = hass
        return entity

    def test_entity_properties(self, mock_conversation_entity):
        """Test entity properties are set correctly."""
        assert mock_conversation_entity._attr_name == "MiniMax Conversation"  # noqa: SLF001
        assert mock_conversation_entity._attr_unique_id == "conversation_subentry_001"  # noqa: SLF001
        assert mock_conversation_entity._attr_supported_features == (  # noqa: SLF001
            conversation.ConversationEntityFeature.CONTROL
        )

    def test_supported_languages_returns_all(self, mock_conversation_entity):
        """Test supported_languages returns MATCH_ALL."""
        assert mock_conversation_entity.supported_languages == MATCH_ALL

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, mock_conversation_entity, hass):
        """Test async_added_to_hass sets the agent."""
        with patch.object(
            minimax_conversation.conversation, "async_set_agent"
        ) as mock_set_agent:
            await mock_conversation_entity.async_added_to_hass()
            mock_set_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass(self, mock_conversation_entity, hass):
        """Test async_will_remove_from_hass unsets the agent."""
        with patch.object(
            minimax_conversation.conversation, "async_unset_agent"
        ) as mock_unset_agent:
            await mock_conversation_entity.async_will_remove_from_hass()
            mock_unset_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_process_success(self, mock_conversation_entity, hass):
        """Test async_process returns successful result."""
        user_input = conversation.ConversationInput(
            text="Hello",
            context=Context(user_id=None),
            conversation_id=None,
            device_id=None,
            satellite_id=None,
            language="en-US",
            agent_id="agent_id",
        )

        with (
            patch.object(
                mock_conversation_entity._client,  # noqa: SLF001
                "async_chat",
                new_callable=AsyncMock,
                return_value=CHAT_RESPONSE_SUCCESS.copy(),
            ),
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
            result = await mock_conversation_entity.async_process(user_input)

        assert result.response.speech["plain"]["speech"] == "Hello! How can I help you?"
        assert result.conversation_id is None

    @pytest.mark.asyncio
    async def test_async_process_with_thinking_content_stripped(
        self, mock_conversation_entity, hass
    ):
        """Test async_process strips thinking content from response."""
        user_input = conversation.ConversationInput(
            text="Hello",
            context=Context(user_id=None),
            conversation_id=None,
            device_id=None,
            satellite_id=None,
            language="en-US",
            agent_id="agent_id",
        )

        response_with_thinking = CHAT_RESPONSE_SUCCESS.copy()
        response_with_thinking["text"] = (
            "<think>I should respond kindly</think>Hello! How can I help you?"
        )

        with (
            patch.object(
                mock_conversation_entity._client,  # noqa: SLF001
                "async_chat",
                new_callable=AsyncMock,
                return_value=response_with_thinking,
            ),
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
            result = await mock_conversation_entity.async_process(user_input)

        assert "<think>" not in result.response.speech["plain"]["speech"]
        assert result.response.speech["plain"]["speech"] == "Hello! How can I help you?"

    @pytest.mark.asyncio
    async def test_async_process_api_error(self, mock_conversation_entity, hass):
        """Test async_process handles API errors gracefully."""
        user_input = conversation.ConversationInput(
            text="Hello",
            context=Context(user_id=None),
            conversation_id=None,
            device_id=None,
            satellite_id=None,
            language="en-US",
            agent_id="agent_id",
        )

        with (
            patch.object(
                mock_conversation_entity._client,  # noqa: SLF001
                "async_chat",
                new_callable=AsyncMock,
                return_value={"success": False, "error": "API Error"},
            ),
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
            result = await mock_conversation_entity.async_process(user_input)

        assert "fejl" in result.response.speech["plain"]["speech"].lower()

    @pytest.mark.asyncio
    async def test_async_process_empty_response(self, mock_conversation_entity, hass):
        """Test async_process handles empty responses."""
        user_input = conversation.ConversationInput(
            text="Hello",
            context=Context(user_id=None),
            conversation_id=None,
            device_id=None,
            satellite_id=None,
            language="en-US",
            agent_id="agent_id",
        )

        with (
            patch.object(
                mock_conversation_entity._client,  # noqa: SLF001
                "async_chat",
                new_callable=AsyncMock,
                return_value={"success": True, "text": "", "tool_calls": []},
            ),
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
            result = await mock_conversation_entity.async_process(user_input)

        assert "ikke" in result.response.speech["plain"]["speech"].lower()


class TestConversationSetup:
    """Test conversation platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_entity(
        self, hass: HomeAssistant, mock_server_response
    ):
        """Test async_setup_entry creates conversation entity."""
        from custom_components.minimax.conversation import async_setup_entry  # noqa: PLC0415, I001

        config_entry = create_mock_minimax_config_entry(hass)
        subentry = MagicMock()
        subentry.subentry_id = "conversation_subentry_001"
        subentry.subentry_type = "conversation"
        subentry.title = "MiniMax Conversation"
        subentry.data = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        config_entry.subentries = {"conversation": subentry}

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
        assert entities_added[0]._attr_name == "MiniMax Conversation"  # noqa: SLF001

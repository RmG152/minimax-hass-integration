"""Tests for MiniMax conversation entity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.minimax import conversation as minimax_conversation
from custom_components.minimax.const import RECOMMENDED_CONVERSATION_OPTIONS
from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL
from homeassistant.core import Context


def _make_subentry(subentry_type="conversation", data=None, title=None):
    """Create a mock config subentry."""
    subentry = MagicMock()
    subentry.subentry_id = f"{subentry_type}_subentry_001"
    subentry.subentry_type = subentry_type
    subentry.title = title or f"MiniMax {subentry_type.title()}"
    subentry.data = data or RECOMMENDED_CONVERSATION_OPTIONS.copy()
    return subentry


def _make_config_entry(entry_id="test_entry"):
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {"api_key": "test_key"}
    entry.subentries = {}
    return entry


class TestMiniMaxConversationEntity:
    """Test MiniMaxConversationEntity."""

    @pytest.fixture
    def mock_memory_store(self):
        """Mock MemoryStore to avoid storage operations."""
        with patch("custom_components.minimax.conversation.MemoryStore") as mock:
            instance = MagicMock()
            instance.async_load = AsyncMock()
            instance.async_add_fact = AsyncMock(return_value="memory_id_123")
            instance.async_get_facts = AsyncMock(return_value=[])
            instance.async_remove_fact = AsyncMock(return_value=True)
            instance.async_clear = AsyncMock()
            instance.async_get_memory_count = AsyncMock(return_value=0)

            def set_hass(hass):
                pass

            instance.set_hass = MagicMock(side_effect=set_hass)

            mock.return_value = instance
            yield instance

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        from tests import create_mock_minimax_client

        return create_mock_minimax_client()

    @pytest.fixture
    def entity(self, hass, mock_client, mock_memory_store):
        """Create a conversation entity."""
        entry = _make_config_entry()
        subentry = _make_subentry()
        entry.subentries = {"conversation": subentry}

        entity = minimax_conversation.MiniMaxConversationEntity(
            entry=entry,
            subentry=subentry,
            client=mock_client,
        )
        entity.hass = hass
        return entity

    def test_entity_properties(self, entity):
        """Test entity properties are set correctly."""
        assert entity._attr_name == "MiniMax Conversation"
        assert entity._attr_unique_id == "conversation_subentry_001"
        assert entity._attr_supported_features == (
            conversation.ConversationEntityFeature.CONTROL
        )

    def test_supported_languages_returns_all(self, entity):
        """Test supported_languages returns MATCH_ALL."""
        assert entity.supported_languages == MATCH_ALL

    @pytest.mark.asyncio
    async def test_async_added_to_hass_sets_agent(self, entity, hass):
        """Test async_added_to_hass sets the agent."""
        with patch.object(conversation, "async_set_agent") as mock_set_agent:
            await entity.async_added_to_hass()
            mock_set_agent.assert_called_once_with(hass, entity.entry, entity)

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass_unsets_agent(self, entity, hass):
        """Test async_will_remove_from_hass unsets the agent."""
        with patch.object(conversation, "async_unset_agent") as mock_unset_agent:
            await entity.async_will_remove_from_hass()
            mock_unset_agent.assert_called_once_with(hass, entity.entry)

    @pytest.mark.asyncio
    async def test_async_process_success(self, entity, hass):
        """Test async_process returns successful result."""
        from tests import CHAT_RESPONSE_SUCCESS

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
            patch(
                "custom_components.minimax.conversation._get_homeassistant_tools",
                return_value=[],
            ),
            patch(
                "custom_components.minimax.conversation._build_system_prompt",
                return_value="You are a helpful assistant.",
            ),
        ):
            entity._client.async_chat = AsyncMock(
                return_value=CHAT_RESPONSE_SUCCESS.copy()
            )
            result = await entity.async_process(user_input)

        assert result.response.speech["plain"]["speech"] == "Hello! How can I help you?"
        assert result.conversation_id is not None

    @pytest.mark.asyncio
    async def test_async_process_strips_thinking_tags(self, entity, hass):
        """Test async_process strips <think> tags from response."""
        from tests import CHAT_RESPONSE_SUCCESS

        user_input = conversation.ConversationInput(
            text="Hello",
            context=Context(user_id=None),
            conversation_id=None,
            device_id=None,
            satellite_id=None,
            language="en-US",
            agent_id="agent_id",
        )

        response = CHAT_RESPONSE_SUCCESS.copy()
        response["text"] = "<think>internal</think>Hello! How can I help you?"

        with (
            patch(
                "custom_components.minimax.conversation._get_homeassistant_tools",
                return_value=[],
            ),
            patch(
                "custom_components.minimax.conversation._build_system_prompt",
                return_value="",
            ),
        ):
            entity._client.async_chat = AsyncMock(return_value=response)
            result = await entity.async_process(user_input)

        assert "<think>" not in result.response.speech["plain"]["speech"]
        assert result.response.speech["plain"]["speech"] == "Hello! How can I help you?"

    @pytest.mark.asyncio
    async def test_async_process_empty_input(self, entity, hass):
        """Test async_process handles empty user input."""
        user_input = conversation.ConversationInput(
            text="",
            context=Context(user_id=None),
            conversation_id=None,
            device_id=None,
            satellite_id=None,
            language="en-US",
            agent_id="agent_id",
        )

        result = await entity.async_process(user_input)

        assert result.response.speech["plain"]["speech"] == "Please say something."

    @pytest.mark.asyncio
    async def test_async_process_api_error_returns_fallback(self, entity, hass):
        """Test async_process handles API errors with fallback message."""
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
            patch(
                "custom_components.minimax.conversation._get_homeassistant_tools",
                return_value=[],
            ),
            patch(
                "custom_components.minimax.conversation._build_system_prompt",
                return_value="",
            ),
        ):
            entity._client.async_chat = AsyncMock(
                return_value={"success": False, "error": "API Error"}
            )
            result = await entity.async_process(user_input)

        assert "Sorry" in result.response.speech["plain"]["speech"]

    @pytest.mark.asyncio
    async def test_async_process_empty_text_uses_fallback(self, entity, hass):
        """Test async_process uses fallback when response text is empty."""
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
            patch(
                "custom_components.minimax.conversation._get_homeassistant_tools",
                return_value=[],
            ),
            patch(
                "custom_components.minimax.conversation._build_system_prompt",
                return_value="",
            ),
        ):
            entity._client.async_chat = AsyncMock(
                return_value={"success": True, "text": "", "tool_calls": []}
            )
            result = await entity.async_process(user_input)

        assert result.response.speech["plain"]["speech"]


class TestConversationHelpers:
    """Test conversation helper functions."""

    def test_estimate_tokens(self):
        """Test _estimate_tokens calculation."""
        assert minimax_conversation._estimate_tokens("Hello") == 1
        assert minimax_conversation._estimate_tokens("Hello world") == 2
        assert minimax_conversation._estimate_tokens("") == 0

    def test_trim_conversation_history_within_limit(self):
        """Test _trim_conversation_history when within token limit."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        trimmed = minimax_conversation._trim_conversation_history(messages, 100000)
        assert trimmed == messages

    def test_trim_conversation_history_removes_excess(self):
        """Test _trim_conversation_history removes messages over limit."""
        messages = [
            {"role": "user", "content": "A" * 1000},
            {"role": "assistant", "content": "B" * 1000},
        ]
        trimmed = minimax_conversation._trim_conversation_history(messages, 100)
        assert len(trimmed) < len(messages)

    def test_trim_conversation_history_empty(self):
        """Test _trim_conversation_history with empty list."""
        assert minimax_conversation._trim_conversation_history([], 1000) == []

    @patch("custom_components.minimax.conversation.llm._get_exposed_entities")
    def test_build_system_prompt_with_exposed_entities(self, mock_get_exposed):
        """Test _build_system_prompt with exposed entity data."""
        mock_get_exposed.return_value = {
            "entities": {
                "light.living_room": {
                    "name": "Living Room Light",
                    "state": "on",
                },
            },
        }
        result = minimax_conversation._build_system_prompt(
            "You are EVA.", self._hass_proxy(), "test_agent"
        )
        assert "You are EVA." in result
        assert "Living Room Light" in result
        assert "on" in result

    @patch("custom_components.minimax.conversation.llm._get_exposed_entities")
    def test_build_system_prompt_with_all_states(self, mock_get_exposed):
        """Test _build_system_prompt shows message when no exposed entities."""
        mock_get_exposed.return_value = {"entities": {}}
        hass = self._hass_proxy()
        result = minimax_conversation._build_system_prompt(
            "You are EVA.", hass, "test_agent"
        )
        assert "You are EVA." in result
        assert "No exposed entities configured" in result

    @patch("custom_components.minimax.conversation.llm._get_exposed_entities")
    def test_build_system_prompt_skips_automation_and_scene(self, mock_get_exposed):
        """Test _build_system_prompt with exposed entities filters properly."""
        mock_get_exposed.return_value = {
            "entities": {
                "light.living_room": {
                    "name": "Living Room",
                    "state": "on",
                },
            },
        }
        hass = self._hass_proxy()
        result = minimax_conversation._build_system_prompt(
            "Prompt.", hass, "test_agent"
        )
        assert "Living Room" in result

    @patch("custom_components.minimax.conversation.llm._get_exposed_entities")
    def test_build_system_prompt_exception_returns_prompt(self, mock_get_exposed):
        """Test _build_system_prompt returns prompt on exception."""
        mock_get_exposed.side_effect = Exception("Boom")
        result = minimax_conversation._build_system_prompt(
            "You are EVA.", self._hass_proxy(), "test_agent"
        )
        assert result == "You are EVA."

    def _hass_proxy(self):
        """Create a minimal hass mock for _build_system_prompt tests."""
        hass = MagicMock()
        hass.states.async_all = MagicMock(return_value=[])
        hass.services = MagicMock()
        hass.services.async_services = MagicMock(return_value={})
        return hass


class TestConversationMemoryTools:
    """Test conversation memory tool execution."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        from tests import create_mock_minimax_client

        return create_mock_minimax_client()

    @pytest.fixture
    def mock_memory_store(self):
        """Mock MemoryStore to avoid storage operations."""
        with patch("custom_components.minimax.conversation.MemoryStore") as mock:
            instance = MagicMock()
            instance.async_load = AsyncMock()
            instance.async_add_fact = AsyncMock(return_value="memory_id_123")
            instance.async_get_facts = AsyncMock(return_value=[])
            instance.async_remove_fact = AsyncMock(return_value=True)
            instance.async_clear = AsyncMock()
            instance.async_get_memory_count = AsyncMock(return_value=0)

            def set_hass(hass):
                pass

            instance.set_hass = MagicMock(side_effect=set_hass)

            mock.return_value = instance
            yield instance

    @pytest.fixture
    def entity(self, hass, mock_client, mock_memory_store):
        """Create a conversation entity."""
        entry = _make_config_entry()
        subentry = _make_subentry()
        entry.subentries = {"conversation": subentry}

        entity = minimax_conversation.MiniMaxConversationEntity(
            entry=entry,
            subentry=subentry,
            client=mock_client,
        )
        entity.hass = hass
        return entity

    @pytest.mark.asyncio
    async def test_remember_fact(self, entity, hass):
        """Test remembering a fact."""
        entity._memory_store.async_add_fact = AsyncMock(return_value="mem_12345678")
        result = await entity._execute_memory_tool(
            "remember_user_fact",
            {"fact": "User likes coffee", "category": "preference"},
        )
        assert "Remembered" in result
        assert "mem_1234" in result

    @pytest.mark.asyncio
    async def test_remember_fact_empty(self, entity, hass):
        """Test remembering an empty fact."""
        result = await entity._execute_memory_tool("remember_user_fact", {"fact": ""})
        assert "No fact provided" in result

    @pytest.mark.asyncio
    async def test_recall_facts(self, entity, hass):
        """Test recalling facts."""
        entity._memory_store.async_get_facts = AsyncMock(
            return_value=[
                {"fact": "User likes coffee", "category": "preference", "id": "1"}
            ]
        )
        result = await entity._execute_memory_tool("recall_user_facts", {})
        assert "coffee" in result

    @pytest.mark.asyncio
    async def test_recall_facts_empty(self, entity, hass):
        """Test recalling facts when none stored."""
        entity._memory_store.async_get_facts = AsyncMock(return_value=[])
        result = await entity._execute_memory_tool("recall_user_facts", {})
        assert "No memories stored" in result

    @pytest.mark.asyncio
    async def test_forget_fact(self, entity, hass):
        """Test forgetting a fact."""
        entity._memory_store.async_remove_fact = AsyncMock(return_value=True)
        result = await entity._execute_memory_tool(
            "forget_user_fact", {"fact": "coffee"}
        )
        assert "Forgotten" in result

    @pytest.mark.asyncio
    async def test_forget_fact_not_found(self, entity, hass):
        """Test forgetting a fact that doesn't exist."""
        entity._memory_store.async_remove_fact = AsyncMock(return_value=False)
        result = await entity._execute_memory_tool(
            "forget_user_fact", {"fact": "nonexistent"}
        )
        assert "Could not find" in result

    @pytest.mark.asyncio
    async def test_forget_all_facts(self, entity, hass):
        """Test forgetting all facts."""
        entity._memory_store.async_get_memory_count = AsyncMock(return_value=5)
        result = await entity._execute_memory_tool("forget_all_user_facts", {})
        assert "Cleared all 5 memories" in result

    @pytest.mark.asyncio
    async def test_memory_store_not_initialized(self, entity, hass):
        """Test memory tools when memory store is None."""
        entity._memory_store = None
        result = await entity._execute_memory_tool("remember_user_fact", {})
        assert "Memory system not initialized" in result

    @pytest.mark.asyncio
    async def test_unknown_memory_command(self, entity, hass):
        """Test unknown memory command."""
        result = await entity._execute_memory_tool("unknown", {})
        assert "Unknown memory command" in result

    @pytest.mark.asyncio
    async def test_execute_tool_calls_service(self, entity, hass):
        """Test executing a HA service tool call."""
        tool_calls = [
            {
                "id": "call_1",
                "name": "light.turn_on",
                "input": {"entity_id": "light.living_room"},
            }
        ]
        results = await entity._execute_tool_calls(tool_calls, [])
        assert len(results) == 1
        assert results[0]["type"] == "tool_result"

    @pytest.mark.asyncio
    async def test_execute_tool_calls_invalid_name(self, entity, hass):
        """Test executing a tool call with invalid name format."""
        tool_calls = [{"id": "call_1", "name": "invalid_tool_name", "input": {}}]
        results = await entity._execute_tool_calls(tool_calls, [])
        assert "Invalid tool name" in results[0]["content"]


class TestConversationCleanup:
    """Test conversation history cleanup."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        from tests import create_mock_minimax_client

        return create_mock_minimax_client()

    @pytest.fixture
    def mock_memory_store(self):
        """Mock MemoryStore to avoid storage operations."""
        with patch("custom_components.minimax.conversation.MemoryStore") as mock:
            instance = MagicMock()
            instance.async_load = AsyncMock()
            instance.async_add_fact = AsyncMock(return_value="memory_id_123")
            instance.async_get_facts = AsyncMock(return_value=[])
            instance.async_remove_fact = AsyncMock(return_value=True)
            instance.async_clear = AsyncMock()
            instance.async_get_memory_count = AsyncMock(return_value=0)

            def set_hass(hass):
                pass

            instance.set_hass = MagicMock(side_effect=set_hass)

            mock.return_value = instance
            yield instance

    @pytest.fixture
    def entity(self, hass, mock_client, mock_memory_store):
        """Create a conversation entity."""
        entry = _make_config_entry()
        subentry = _make_subentry()
        entry.subentries = {"conversation": subentry}

        entity = minimax_conversation.MiniMaxConversationEntity(
            entry=entry,
            subentry=subentry,
            client=mock_client,
        )
        entity.hass = hass
        return entity

    def test_cleanup_expired_removes_old_conversations(self, entity):
        """Test cleanup removes expired conversations."""
        import time

        entity._conversation_history = {
            "old": ([], time.time() - 3600),
            "new": ([], time.time()),
        }
        entity._expiry_minutes = 1
        entity._cleanup_expired_conversations()
        assert "old" not in entity._conversation_history
        assert "new" in entity._conversation_history

    def test_cleanup_expired_enforces_max_count(self, entity):
        """Test cleanup enforces max_conversations limit."""
        entity._max_conversations = 2
        entity._expiry_minutes = 0
        entity._conversation_history = {f"c{i}": ([], float(i)) for i in range(5)}
        entity._cleanup_expired_conversations()
        assert len(entity._conversation_history) <= 2

    def test_cleanup_expired_keeps_under_limit(self, entity):
        """Test cleanup does nothing when under limit."""
        entity._expiry_minutes = 0
        entity._conversation_history = {"c1": ([], 100.0)}
        entity._cleanup_expired_conversations()
        assert "c1" in entity._conversation_history


class TestGetHomeAssistantTools:
    """Test _get_homeassistant_tools function."""

    def test_with_required_field_and_entity_id_injection(self, hass):
        """Test tool generation: required field, entity_id auto-inject."""
        hass.services.async_services.return_value = {
            "light": {
                "turn_on": {
                    "description": "Turn on light",
                    "fields": {
                        "brightness": {
                            "description": "Brightness level",
                            "required": True,
                            "example": 255,
                        },
                    },
                },
            },
        }
        tools = minimax_conversation._get_homeassistant_tools(hass)
        assert len(tools) == 1
        tool = tools[0]
        assert tool["name"] == "light.turn_on"
        assert tool["input_schema"]["required"] == ["brightness"]
        assert tool["input_schema"]["properties"]["brightness"]["type"] == "int"
        assert "entity_id" in tool["input_schema"]["properties"]

    def test_with_entity_id_already_present(self, hass):
        """Test tool generation when entity_id already in fields."""
        hass.services.async_services.return_value = {
            "light": {
                "turn_on": {
                    "description": "Turn on light",
                    "fields": {
                        "entity_id": {
                            "description": "Target entity",
                        },
                    },
                },
            },
        }
        tools = minimax_conversation._get_homeassistant_tools(hass)
        assert len(tools) == 1
        assert "entity_id" in tools[0]["input_schema"]["properties"]

    def test_with_non_key_domain_skipped(self, hass):
        """Test non-key domains are skipped in the first pass."""
        hass.services.async_services.return_value = {
            "sensor": {
                "some_service": {
                    "description": "A sensor service",
                    "fields": {},
                },
            },
        }
        tools = minimax_conversation._get_homeassistant_tools(hass)
        assert len(tools) == 0

    def test_with_private_service_skipped(self, hass):
        """Test private services (starting with _) are skipped."""
        hass.services.async_services.return_value = {
            "light": {
                "_private": {
                    "description": "Private service",
                    "fields": {},
                },
            },
        }
        tools = minimax_conversation._get_homeassistant_tools(hass)
        assert len(tools) == 0

    def test_with_api_error_returns_empty(self, hass):
        """Test that API errors return empty list."""
        hass.services.async_services.side_effect = Exception("Service error")
        tools = minimax_conversation._get_homeassistant_tools(hass)
        assert tools == []

    def test_with_field_having_schema(self, hass):
        """Test field_type stays string when schema is set."""
        hass.services.async_services.return_value = {
            "light": {
                "turn_on": {
                    "description": "Turn on",
                    "fields": {
                        "target": {
                            "description": "Target",
                            "schema": {"type": "string"},
                        },
                    },
                },
            },
        }
        tools = minimax_conversation._get_homeassistant_tools(hass)
        assert len(tools) == 1
        assert tools[0]["input_schema"]["properties"]["target"]["type"] == "string"


class TestConversationSetup:
    """Test conversation platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_entity(self, hass):
        """Test async_setup_entry creates conversation entity."""
        from tests import create_mock_minimax_client

        entry = _make_config_entry()
        subentry = _make_subentry()
        entry.subentries = {"conversation": subentry}

        mock_client = create_mock_minimax_client()
        entry.runtime_data = mock_client

        entities_added = []

        def mock_add_entities(entities, config_subentry_id=None):
            entities_added.extend(entities)

        with patch("custom_components.minimax.conversation.MemoryStore"):
            await minimax_conversation.async_setup_entry(hass, entry, mock_add_entities)

        assert len(entities_added) == 1
        assert entities_added[0]._attr_name == "MiniMax Conversation"

    @pytest.mark.asyncio
    async def test_async_setup_entry_skips_non_conversation(self, hass):
        """Test async_setup_entry skips non-conversation subentries."""
        from tests import create_mock_minimax_client

        entry = _make_config_entry()
        tts_sub = _make_subentry(subentry_type="tts")
        entry.subentries = {"tts": tts_sub}

        mock_client = create_mock_minimax_client()
        entry.runtime_data = mock_client

        entities_added = []

        def mock_add_entities(entities, config_subentry_id=None):
            entities_added.extend(entities)

        await minimax_conversation.async_setup_entry(hass, entry, mock_add_entities)

        assert len(entities_added) == 0

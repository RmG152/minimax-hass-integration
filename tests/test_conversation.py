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
    def test_build_system_prompt_fallback_to_all_states_filters_automation_scene(
        self, mock_get_exposed
    ):
        """Test fallback to all states filters out automation. and scene. entities."""
        mock_get_exposed.return_value = {"entities": {}}
        light_state = MagicMock()
        light_state.entity_id = "light.living_room"
        light_state.name = "Living Room"
        light_state.state = "on"
        automation_state = MagicMock()
        automation_state.entity_id = "automation.morning"
        automation_state.name = "Morning"
        automation_state.state = "off"
        scene_state = MagicMock()
        scene_state.entity_id = "scene.movie"
        scene_state.name = "Movie"
        scene_state.state = "scening"
        hass = MagicMock()
        hass.states.async_all = MagicMock(
            return_value=[light_state, automation_state, scene_state]
        )
        hass.services = MagicMock()
        hass.services.async_services = MagicMock(return_value={})

        result = minimax_conversation._build_system_prompt(
            "You are EVA.", hass, "test_agent"
        )
        assert "You are EVA." in result
        assert "Living Room" in result
        assert "Morning" not in result
        assert "Movie" not in result

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


class TestConversationEntityExtra:
    """Extra coverage for MiniMaxConversationEntity paths."""

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
            instance.set_hass = MagicMock()
            mock.return_value = instance
            yield instance

    @pytest.fixture
    def entity(self, hass, mock_client, mock_memory_store):
        """Create a conversation entity."""
        entry = _make_config_entry()
        subentry = _make_subentry()
        entry.subentries = {"conversation": subentry}
        entity = minimax_conversation.MiniMaxConversationEntity(
            entry=entry, subentry=subentry, client=mock_client
        )
        entity.hass = hass
        return entity

    @pytest.mark.asyncio
    async def test_async_added_to_hass_with_memory(self, entity, hass):
        """Test async_added_to_hass loads memories when memory is enabled."""
        with patch.object(conversation, "async_set_agent"):
            await entity.async_added_to_hass()
        entity._memory_store.set_hass.assert_called_once_with(hass)
        entity._memory_store.async_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tools_caches(self, entity, hass):
        """Test _get_tools caches results."""
        with patch(
            "custom_components.minimax.conversation._get_homeassistant_tools",
            return_value=[],
        ) as mock_get:
            tools1 = entity._get_tools()
            tools2 = entity._get_tools()
        assert tools1 == tools2
        mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tools_with_memory_extends(self, entity):
        """Test _get_tools appends memory tools when memory is enabled."""
        with patch(
            "custom_components.minimax.conversation._get_homeassistant_tools",
            return_value=[],
        ):
            tools = entity._get_tools()
        tool_names = [t["name"] for t in tools]
        assert "remember_user_fact" in tool_names
        assert "recall_user_facts" in tool_names
        assert "forget_user_fact" in tool_names
        assert "forget_all_user_facts" in tool_names

    @pytest.mark.asyncio
    async def test_get_memory_section_no_store_returns_empty(self, entity):
        """Test _get_memory_section returns empty string when store is None."""
        entity._memory_store = None
        result = await entity._get_memory_section()
        assert result == ""

    @pytest.mark.asyncio
    async def test_get_memory_section_no_facts_returns_empty(self, entity):
        """Test _get_memory_section returns empty when no memories."""
        entity._memory_store.async_get_facts = AsyncMock(return_value=[])
        result = await entity._get_memory_section()
        assert result == ""

    @pytest.mark.asyncio
    async def test_get_memory_section_with_facts(self, entity):
        """Test _get_memory_section includes stored facts."""
        entity._memory_store.async_get_facts = AsyncMock(
            return_value=[
                {"fact": "User likes coffee"},
                {"fact": "User owns a dog"},
            ]
        )
        result = await entity._get_memory_section()
        assert "Known User Facts" in result
        assert "User likes coffee" in result
        assert "User owns a dog" in result

    @pytest.mark.asyncio
    async def test_get_memory_section_exception_returns_empty(self, entity):
        """Test _get_memory_section returns empty on exception."""
        entity._memory_store.async_get_facts = AsyncMock(
            side_effect=Exception("memory boom")
        )
        result = await entity._get_memory_section()
        assert result == ""

    @pytest.mark.asyncio
    async def test_chat_with_api_tool_call_recursive(self, entity, mock_client):
        """Test _chat_with_api executes tool calls recursively."""
        tool_response = {
            "success": True,
            "content": [
                {"type": "text", "text": "Turning on light."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "light.turn_on",
                    "input": {"entity_id": "light.living_room"},
                },
            ],
            "text": "Turning on light.",
            "tool_calls": [
                {
                    "id": "toolu_1",
                    "name": "light.turn_on",
                    "input": {"entity_id": "light.living_room"},
                }
            ],
            "stop_reason": "tool_use",
        }
        final_response = {
            "success": True,
            "content": [{"type": "text", "text": "Light is on."}],
            "text": "Light is on.",
            "tool_calls": [],
            "stop_reason": "end_turn",
        }
        mock_client.async_chat = AsyncMock(side_effect=[tool_response, final_response])
        with patch(
            "custom_components.minimax.conversation._call_service",
            AsyncMock(return_value={"success": True, "result": "ok"}),
        ):
            text, _messages = await entity._chat_with_api(
                "system",
                [{"role": "user", "content": "turn on light"}],
                [],
                "model",
            )
        assert text == "Light is on."

    @pytest.mark.asyncio
    async def test_chat_with_api_tool_id_mismatch(self, entity, mock_client):
        """Test _chat_with_api handles tool id mismatch by returning prior text."""
        tool_response = {
            "success": True,
            "content": [
                {"type": "text", "text": "Here is info."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "remember_user_fact",
                    "input": {"fact": "User likes coffee"},
                },
            ],
            "text": "Here is info.",
            "tool_calls": [
                {
                    "id": "toolu_1",
                    "name": "remember_user_fact",
                    "input": {"fact": "User likes coffee"},
                }
            ],
            "stop_reason": "tool_use",
        }
        call_count = {"n": 0}

        def chat_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return tool_response
            raise RuntimeError("tool id not found")

        mock_client.async_chat = AsyncMock(side_effect=chat_side_effect)
        with patch.object(entity, "_execute_tool_calls", AsyncMock(return_value=[])):
            text, _ = await entity._chat_with_api(
                "system",
                [{"role": "user", "content": "remember"}],
                [],
                "model",
            )
        assert text == "Here is info."

    @pytest.mark.asyncio
    async def test_chat_with_api_tool_id_mismatch_no_text(self, entity, mock_client):
        """Test tool id mismatch returns fallback text when no text parts."""
        tool_response = {
            "success": True,
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "remember_user_fact",
                    "input": {"fact": "User likes coffee"},
                },
            ],
            "text": "",
            "tool_calls": [
                {
                    "id": "toolu_1",
                    "name": "remember_user_fact",
                    "input": {"fact": "User likes coffee"},
                }
            ],
            "stop_reason": "tool_use",
        }
        call_count = {"n": 0}

        def chat_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return tool_response
            raise RuntimeError("tool id not found")

        mock_client.async_chat = AsyncMock(side_effect=chat_side_effect)
        with patch.object(entity, "_execute_tool_calls", AsyncMock(return_value=[])):
            text, _ = await entity._chat_with_api(
                "system",
                [{"role": "user", "content": "remember"}],
                [],
                "model",
            )
        assert "trouble answering" in text

    @pytest.mark.asyncio
    async def test_chat_with_api_text_only_with_tool_use(self, entity, mock_client):
        """Test _chat_with_api returns text when no tool calls are executed."""
        tool_response = {
            "success": True,
            "content": [{"type": "text", "text": "Some text"}],
            "text": "Some text",
            "tool_calls": [],
            "stop_reason": "end_turn",
        }
        mock_client.async_chat = AsyncMock(return_value=tool_response)
        text, _ = await entity._chat_with_api("system", [], [], "model")
        assert text == "Some text"

    @pytest.mark.asyncio
    async def test_chat_with_api_error_raises(self, entity, mock_client):
        """Test _chat_with_api raises on API error."""
        from custom_components.minimax.api import MiniMaxApiClientError

        mock_client.async_chat = AsyncMock(
            return_value={"success": False, "error": "boom"}
        )
        with pytest.raises(MiniMaxApiClientError):
            await entity._chat_with_api("system", [], [], "model")

    @pytest.mark.asyncio
    async def test_execute_tool_calls_calls_service(self, entity, hass):
        """Test _execute_tool_calls invokes _call_service for service tools."""
        tool_calls = [
            {
                "id": "call_1",
                "name": "light.turn_on",
                "input": {"entity_id": "light.living_room"},
            }
        ]
        with patch(
            "custom_components.minimax.conversation._call_service",
            AsyncMock(return_value={"success": True}),
        ) as mock_call:
            results = await entity._execute_tool_calls(tool_calls, [])
        assert results[0]["type"] == "tool_result"
        assert results[0]["tool_use_id"] == "call_1"
        mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_calls_service_returns_error(self, entity, hass):
        """Test _execute_tool_calls handles service errors."""
        tool_calls = [
            {
                "id": "call_1",
                "name": "light.turn_on",
                "input": {"entity_id": "light.broken"},
            }
        ]
        with patch(
            "custom_components.minimax.conversation._call_service",
            AsyncMock(return_value={"success": False, "error": "service boom"}),
        ):
            results = await entity._execute_tool_calls(tool_calls, [])
        assert "service boom" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_no_name_skipped(self, entity):
        """Test _execute_tool_calls skips calls with no name."""
        results = await entity._execute_tool_calls(
            [{"id": "x", "name": "", "input": {}}], []
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_call_service_success(self):
        """Test _call_service returns success dict."""
        hass = MagicMock()
        hass.services.async_call = AsyncMock(return_value={"result": "ok"})
        result = await minimax_conversation._call_service(
            hass, "light", "turn_on", {"entity_id": "light.x"}
        )
        assert result == {"success": True, "result": {"result": "ok"}}

    @pytest.mark.asyncio
    async def test_call_service_exception(self):
        """Test _call_service returns error dict on exception."""
        hass = MagicMock()
        hass.services.async_call = AsyncMock(side_effect=Exception("boom"))
        result = await minimax_conversation._call_service(
            hass, "light", "turn_on", {"entity_id": "light.x"}
        )
        assert result["success"] is False
        assert "boom" in result["error"]

    @pytest.mark.asyncio
    async def test_get_homeassistant_tools_empty_when_no_key_domains(self, hass):
        """Test _get_homeassistant_tools returns empty when no key domains match."""
        hass.services.async_services.return_value = {
            "not_a_key_domain": {
                "service": {
                    "description": "x",
                    "fields": {},
                }
            }
        }
        tools = minimax_conversation._get_homeassistant_tools(hass)
        assert tools == []

    @pytest.mark.asyncio
    async def test_forget_user_fact_no_fact_arg(self, entity):
        """Test _execute_memory_tool with empty fact for forget."""
        result = await entity._execute_memory_tool("forget_user_fact", {"fact": ""})
        assert "No fact specified" in result

    @pytest.mark.asyncio
    async def test_execute_tool_calls_no_domain_separator(self, entity):
        """Test _execute_tool_calls marks invalid name without dot separator."""
        results = await entity._execute_tool_calls(
            [{"id": "call_1", "name": "no_dot", "input": {}}], []
        )
        assert "Invalid tool name" in results[0]["content"]


class TestConversationEntityCoverage:
    """Additional tests to close remaining coverage gaps."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock API client."""
        from custom_components.minimax.api import MiniMaxApiClient

        client = MagicMock(spec=MiniMaxApiClient)
        client.async_chat = AsyncMock()
        client.async_get_supported_voices = MagicMock(return_value=[])
        return client

    @pytest.fixture
    def mock_memory_store(self):
        """Create a mock memory store."""
        with patch("custom_components.minimax.conversation.MemoryStore") as mock:
            instance = MagicMock()
            instance.async_add_fact = AsyncMock(return_value="mem_id_1")
            instance.async_get_facts = AsyncMock(
                return_value=[
                    {"id": "m1", "fact": "User likes coffee", "category": "preference"}
                ]
            )
            instance.async_remove_fact = AsyncMock(return_value=True)
            instance.async_clear = AsyncMock()
            instance.async_get_memory_count = AsyncMock(return_value=3)
            instance.set_hass = MagicMock()
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

    def test_get_homeassistant_tools_non_key_domain_skipped(self, hass):
        """Domains not in key_domains are skipped (line 120)."""
        hass.services.async_services.return_value = {
            "homeassistant": {
                "turn_on": {
                    "description": "ok",
                    "fields": {"entity_id": {"selector": {"entity_id": {}}}},
                }
            },
            "other_random_domain": {
                "service": {
                    "description": "x",
                    "fields": {},
                }
            },
        }
        tools = minimax_conversation._get_homeassistant_tools(hass)
        names = [t["name"] for t in tools]
        assert all("other_random_domain" not in n for n in names)

    def test_trim_conversation_history_handles_list_content(self):
        """Test _trim_conversation_history handles list content (line 189)."""
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello "},
                    {"type": "text", "text": "world"},
                    {"type": "image", "source": {"data": "ignored"}},
                ],
            }
        ]
        result = minimax_conversation._trim_conversation_history(msgs, max_tokens=100)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_execute_tool_calls_remember_fact(self, entity, mock_memory_store):
        """Test _execute_tool_calls with remember_user_fact (lines 393-401)."""
        results = await entity._execute_tool_calls(
            [
                {
                    "id": "call_mem_1",
                    "name": "remember_user_fact",
                    "input": {"fact": "User likes tea", "category": "preference"},
                }
            ],
            [],
        )
        assert len(results) == 1
        assert results[0]["type"] == "tool_result"
        assert results[0]["tool_use_id"] == "call_mem_1"
        mock_memory_store.async_add_fact.assert_awaited_once_with(
            "User likes tea", "preference"
        )

    @pytest.mark.asyncio
    async def test_execute_tool_calls_forget_all_facts(self, entity, mock_memory_store):
        """Test _execute_tool_calls with forget_all_user_facts tool."""
        results = await entity._execute_tool_calls(
            [{"id": "call_forget", "name": "forget_all_user_facts", "input": {}}],
            [],
        )
        assert len(results) == 1
        mock_memory_store.async_clear.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_with_api_propagates_non_tool_id_error(
        self, entity, mock_client
    ):
        """Test _chat_with_api re-raises non-tool-id errors (line 562)."""
        call_count = {"n": 0}

        def chat_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {
                    "success": True,
                    "content": [{"type": "text", "text": "First"}],
                    "tool_calls": [
                        {"id": "tc_1", "name": "light.turn_on", "input": {}}
                    ],
                }
            raise RuntimeError("Some unexpected error")

        mock_client.async_chat = AsyncMock(side_effect=chat_side_effect)

        with pytest.raises(RuntimeError, match="Some unexpected error"):
            await entity._chat_with_api(
                system_prompt="",
                messages=[],
                tools=[],
                model="test-model",
            )

    @pytest.mark.asyncio
    async def test_memory_section_appended_to_system_prompt(
        self, entity, hass, mock_client
    ):
        """Test that memory section is appended to system_prompt (line 640)."""
        entity._memory_enabled = True
        entity._memory_store = MagicMock()
        entity._memory_store.async_get_facts = AsyncMock(
            return_value=[
                {"id": "m1", "fact": "User likes coffee", "category": "preference"}
            ]
        )

        mock_client.async_chat = AsyncMock(
            return_value={"success": True, "text": "Sure thing!"}
        )

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
            result = await entity.async_process(user_input)

        assert result.response.speech["plain"]["speech"] == "Sure thing!"

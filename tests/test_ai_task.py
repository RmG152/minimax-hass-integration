"""Tests for MiniMax AI Task entity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.minimax import ai_task as minimax_ai_task
from custom_components.minimax.const import (
    CONF_CHAT_MODEL,
    CONF_RECOMMENDED,
    RECOMMENDED_AI_TASK_MAX_TOKENS,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
)
from homeassistant.components import ai_task
from homeassistant.exceptions import HomeAssistantError


def _make_subentry(data=None, title=None, subentry_type="ai_task_data"):
    """Create a mock AI task subentry."""
    subentry = MagicMock()
    subentry.subentry_id = f"{subentry_type}_subentry_001"
    subentry.subentry_type = subentry_type
    subentry.title = title or "MiniMax AI Task"
    subentry.data = data or RECOMMENDED_AI_TASK_OPTIONS.copy()
    return subentry


def _make_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"api_key": "test_key"}
    entry.subentries = {}
    return entry


def _make_chat_log(text_instructions="Test instructions"):
    """Create a mock chat log with a system content and the user instructions."""
    from homeassistant.components import conversation

    system_content = MagicMock()
    system_content.role = "system"
    system_content.content = "You are a helpful assistant."

    user_content = conversation.UserContent(
        content=text_instructions,
        attachments=[],
    )

    log = MagicMock()
    log.content = [system_content, user_content]
    log.conversation_id = "conv_001"

    def _add_user(content):
        log.content.append(content)

    log.async_add_user_content = MagicMock(side_effect=_add_user)
    log.async_add_assistant_content_without_tools = MagicMock()
    return log


class TestMiniMaxAITaskEntityInit:
    """Test MiniMaxAITaskEntity initialization."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        from tests import create_mock_minimax_client

        return create_mock_minimax_client()

    def test_init_recommended_enables_image(self, mock_client):
        """Test init with recommended options enables image generation."""
        entry = _make_config_entry()
        subentry = _make_subentry(data=RECOMMENDED_AI_TASK_OPTIONS.copy())
        entity = minimax_ai_task.MiniMaxAITaskEntity(entry, subentry, mock_client)
        assert entity._attr_name == "MiniMax AI Task"
        assert entity._attr_unique_id == "ai_task_data_subentry_001"
        assert (
            entity._attr_supported_features & ai_task.AITaskEntityFeature.GENERATE_IMAGE
        ) == ai_task.AITaskEntityFeature.GENERATE_IMAGE

    def test_init_image_model_enables_image(self, mock_client):
        """Test init with image model name enables image generation."""
        entry = _make_config_entry()
        data = {CONF_CHAT_MODEL: "image-01-image", CONF_RECOMMENDED: False}
        subentry = _make_subentry(data=data)
        entity = minimax_ai_task.MiniMaxAITaskEntity(entry, subentry, mock_client)
        assert (
            entity._attr_supported_features & ai_task.AITaskEntityFeature.GENERATE_IMAGE
        ) == ai_task.AITaskEntityFeature.GENERATE_IMAGE

    def test_init_non_recommended_keeps_data_only(self, mock_client):
        """Test init with non-recommended and no image model keeps data-only."""
        entry = _make_config_entry()
        data = {CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL, CONF_RECOMMENDED: False}
        subentry = _make_subentry(data=data)
        entity = minimax_ai_task.MiniMaxAITaskEntity(entry, subentry, mock_client)
        assert (
            entity._attr_supported_features & ai_task.AITaskEntityFeature.GENERATE_IMAGE
        ) == 0


class TestAITaskSetup:
    """Test AI Task platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_entity(self, hass):
        """Test async_setup_entry creates the AI task entity."""
        from tests import create_mock_minimax_client

        entry = _make_config_entry()
        subentry = _make_subentry()
        entry.subentries = {"ai_task_data": subentry}
        entry.runtime_data = create_mock_minimax_client()

        entities_added = []

        def mock_add_entities(entities, config_subentry_id=None):
            entities_added.extend(entities)

        await minimax_ai_task.async_setup_entry(hass, entry, mock_add_entities)
        assert len(entities_added) == 1
        assert entities_added[0]._attr_name == "MiniMax AI Task"

    @pytest.mark.asyncio
    async def test_async_setup_entry_skips_non_ai_task(self, hass):
        """Test async_setup_entry ignores non-ai_task subentries."""
        from tests import create_mock_minimax_client

        entry = _make_config_entry()
        other = MagicMock()
        other.subentry_id = "conv_001"
        other.subentry_type = "conversation"
        other.title = "Conversation"
        other.data = {}
        entry.subentries = {"conversation": other}
        entry.runtime_data = create_mock_minimax_client()

        entities_added = []

        def mock_add_entities(entities, config_subentry_id=None):
            entities_added.extend(entities)

        await minimax_ai_task.async_setup_entry(hass, entry, mock_add_entities)
        assert entities_added == []


class TestGenerateDataText:
    """Test _async_generate_data for plain text (no structure)."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        from tests import create_mock_minimax_client

        return create_mock_minimax_client()

    @pytest.fixture
    def entity(self, mock_client):
        """Create an AI task entity."""
        entry = _make_config_entry()
        subentry = _make_subentry()
        return minimax_ai_task.MiniMaxAITaskEntity(entry, subentry, mock_client)

    @pytest.mark.asyncio
    async def test_text_only_returns_raw(self, entity, mock_client):
        """Test text-only result returns raw text without parsing."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Say hello"
        task.structure = None
        task.attachments = []
        chat_log = _make_chat_log("Say hello")

        mock_client.async_chat = AsyncMock(
            return_value={"success": True, "text": "Hello there!"}
        )

        result = await entity._async_generate_data(task, chat_log)
        assert result.data == "Hello there!"

    @pytest.mark.asyncio
    async def test_text_only_strips_thinking_tags(self, entity, mock_client):
        """Test <think> tags are stripped from text result."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Say hello"
        task.structure = None
        task.attachments = []
        chat_log = _make_chat_log("Say hello")

        mock_client.async_chat = AsyncMock(
            return_value={"success": True, "text": "<think>hidden</think>Hello"}
        )

        result = await entity._async_generate_data(task, chat_log)
        assert "<think>" not in result.data
        assert result.data == "Hello"


class TestGenerateDataStructure:
    """Test _async_generate_data with JSON structure."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        from tests import create_mock_minimax_client

        return create_mock_minimax_client()

    @pytest.fixture
    def entity(self, mock_client):
        """Create an AI task entity."""
        entry = _make_config_entry()
        subentry = _make_subentry()
        return minimax_ai_task.MiniMaxAITaskEntity(entry, subentry, mock_client)

    @pytest.mark.asyncio
    async def test_json_response_parsed(self, entity, mock_client):
        """Test that JSON in code block is parsed successfully."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Provide data"
        task.attachments = []
        task.structure = vol.Schema(
            {
                vol.Required("name"): str,
                vol.Required("age"): int,
            }
        )
        chat_log = _make_chat_log("Provide data")

        mock_client.async_chat = AsyncMock(
            return_value={
                "success": True,
                "text": '```json\n{"name": "Alice", "age": 30}\n```',
            }
        )

        result = await entity._async_generate_data(task, chat_log)
        assert result.data == {"name": "Alice", "age": 30}

    @pytest.mark.asyncio
    async def test_json_response_raw_parsed(self, entity, mock_client):
        """Test raw JSON object (no fence) is parsed."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Provide data"
        task.attachments = []
        task.structure = vol.Schema({vol.Required("value"): str})
        chat_log = _make_chat_log("Provide data")

        mock_client.async_chat = AsyncMock(
            return_value={"success": True, "text": '{"value": "ok"}'}
        )

        result = await entity._async_generate_data(task, chat_log)
        assert result.data == {"value": "ok"}

    @pytest.mark.asyncio
    async def test_json_response_array_parsed(self, entity, mock_client):
        """Test raw JSON array literal is parsed via fallback."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Provide data"
        task.attachments = []
        task.structure = vol.Schema({vol.Required("items"): list})
        chat_log = _make_chat_log("Provide data")

        mock_client.async_chat = AsyncMock(
            return_value={
                "success": True,
                "text": 'Here you go: {"items": [1, 2, 3]} cheers!',
            }
        )

        result = await entity._async_generate_data(task, chat_log)
        assert result.data == {"items": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_json_parse_failure_raises(self, entity, mock_client):
        """Test invalid JSON raises HomeAssistantError."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Provide data"
        task.attachments = []
        task.structure = vol.Schema({vol.Required("x"): int})
        chat_log = _make_chat_log("Provide data")

        mock_client.async_chat = AsyncMock(
            return_value={"success": True, "text": "not json at all"}
        )

        with pytest.raises(HomeAssistantError, match="Sorry, I had a problem"):
            await entity._async_generate_data(task, chat_log)

    @pytest.mark.asyncio
    async def test_empty_text_with_structure_raises(self, entity, mock_client):
        """Test empty response with structure raises error."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Provide data"
        task.attachments = []
        task.structure = vol.Schema({vol.Required("x"): int})
        chat_log = _make_chat_log("Provide data")

        mock_client.async_chat = AsyncMock(return_value={"success": True, "text": ""})

        with pytest.raises(HomeAssistantError, match="empty response"):
            await entity._async_generate_data(task, chat_log)

    @pytest.mark.asyncio
    async def test_api_error_raises(self, entity, mock_client):
        """Test API error raises HomeAssistantError."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Provide data"
        task.attachments = []
        task.structure = None
        chat_log = _make_chat_log("Provide data")

        mock_client.async_chat = AsyncMock(
            return_value={"success": False, "error": "boom"}
        )

        with pytest.raises(HomeAssistantError, match="Sorry, I had a problem"):
            await entity._async_generate_data(task, chat_log)

    @pytest.mark.asyncio
    async def test_unexpected_exception_raises(self, entity, mock_client):
        """Test non-API exception is wrapped as HomeAssistantError."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Provide data"
        task.attachments = []
        task.structure = None
        chat_log = _make_chat_log("Provide data")

        mock_client.async_chat = AsyncMock(side_effect=Exception("unexpected"))

        with pytest.raises(HomeAssistantError, match="Sorry, I had a problem"):
            await entity._async_generate_data(task, chat_log)

    @pytest.mark.asyncio
    async def test_attachments_included_in_prompt(self, entity, mock_client):
        """Test that attachments populate chat log user content."""
        attachment = MagicMock()
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Analyze"
        task.attachments = [attachment]
        task.structure = None
        chat_log = _make_chat_log("Analyze")

        mock_client.async_chat = AsyncMock(return_value={"success": True, "text": "ok"})

        await entity._async_generate_data(task, chat_log)
        chat_log.async_add_user_content.assert_called_once()
        call_args = chat_log.async_add_user_content.call_args[0][0]
        assert call_args.content == "Analyze"
        assert call_args.attachments == [attachment]

    @pytest.mark.asyncio
    async def test_chat_called_with_recommended_max_tokens(self, entity, mock_client):
        """Test client is called with the recommended max tokens."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Provide data"
        task.attachments = []
        task.structure = None
        chat_log = _make_chat_log("Provide data")

        mock_client.async_chat = AsyncMock(return_value={"success": True, "text": "ok"})

        await entity._async_generate_data(task, chat_log)
        call_kwargs = mock_client.async_chat.call_args[1]
        assert call_kwargs["max_tokens"] == RECOMMENDED_AI_TASK_MAX_TOKENS
        assert all(m["role"] == "user" for m in call_kwargs["messages"])
        assert all(m["content"] == "Provide data" for m in call_kwargs["messages"])
        assert call_kwargs["system_prompt"] == "You are a helpful assistant."


class TestGenerateImage:
    """Test _async_generate_image."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        from tests import create_mock_minimax_client

        return create_mock_minimax_client()

    @pytest.fixture
    def entity(self, mock_client):
        """Create an AI task entity."""
        entry = _make_config_entry()
        subentry = _make_subentry()
        return minimax_ai_task.MiniMaxAITaskEntity(entry, subentry, mock_client)

    @pytest.mark.asyncio
    async def test_generate_image_success(self, entity, mock_client):
        """Test successful image generation returns image data."""
        task = MagicMock(spec=ai_task.GenImageTask)
        task.instructions = "A cat"
        task.attachments = []
        chat_log = MagicMock()
        chat_log.async_add_assistant_content_without_tools = MagicMock()

        mock_client.async_image_generation = AsyncMock(return_value=b"fake_png")

        result = await entity._async_generate_image(task, chat_log)
        assert result.image_data == b"fake_png"
        assert result.mime_type == "image/png"
        call_kwargs = mock_client.async_image_generation.call_args[1]
        assert call_kwargs["prompt"] == "A cat"
        assert call_kwargs["aspect_ratio"] == "1:1"

    @pytest.mark.asyncio
    async def test_generate_image_with_attachments_appends_marker(
        self, entity, mock_client
    ):
        """Test that attachments append an image marker to the prompt."""
        task = MagicMock(spec=ai_task.GenImageTask)
        task.instructions = "A cat"
        task.attachments = [MagicMock()]
        chat_log = MagicMock()
        chat_log.async_add_assistant_content_without_tools = MagicMock()

        mock_client.async_image_generation = AsyncMock(return_value=b"png")

        await entity._async_generate_image(task, chat_log)
        prompt = mock_client.async_image_generation.call_args[1]["prompt"]
        assert "[Image attachments provided]" in prompt
        assert prompt.startswith("A cat")

    @pytest.mark.asyncio
    async def test_generate_image_error_raises(self, entity, mock_client):
        """Test image generation error raises HomeAssistantError."""
        task = MagicMock(spec=ai_task.GenImageTask)
        task.instructions = "A cat"
        task.attachments = []
        chat_log = MagicMock()
        chat_log.async_add_assistant_content_without_tools = MagicMock()

        mock_client.async_image_generation = AsyncMock(
            side_effect=Exception("img boom")
        )

        with pytest.raises(HomeAssistantError, match="Error generating image"):
            await entity._async_generate_image(task, chat_log)


class TestSchemaHelpers:
    """Test schema helper functions."""

    def test_raise_parse_error(self):
        """Test _raise_parse_error raises HomeAssistantError."""
        with pytest.raises(HomeAssistantError):
            minimax_ai_task._raise_parse_error()

    def test_extract_fenced_code_json(self):
        """Test extracting JSON from ```json fence."""
        text = '```json\n{"a": 1}\n```'
        assert minimax_ai_task._extract_fenced_code(text) == '{"a": 1}'

    def test_extract_fenced_code_plain(self):
        """Test extracting content from plain fence."""
        text = '```\n{"a": 1}\n```'
        assert minimax_ai_task._extract_fenced_code(text) == '{"a": 1}'

    def test_extract_fenced_code_no_match(self):
        """Test no fence returns None."""
        assert minimax_ai_task._extract_fenced_code("no code block") is None

    def test_extract_json_literal_object(self):
        """Test extracting a JSON object literal from text."""
        text = 'Sure, here is the JSON: {"a": 1} enjoy!'
        result = minimax_ai_task._extract_json_literal(text)
        assert result == '{"a": 1}'

    def test_extract_json_literal_array(self):
        """Test extracting a JSON array literal from text."""
        text = "Got it: [1, 2, 3] thanks"
        result = minimax_ai_task._extract_json_literal(text)
        assert result == "[1, 2, 3]"

    def test_extract_json_literal_no_match(self):
        """Test no literal returns None."""
        assert minimax_ai_task._extract_json_literal("nothing here") is None

    def test_extract_json_uses_fenced_first(self):
        """Test fenced code is preferred when both are present."""
        text = '```json\n{"a": 1}\n``` and also {"b": 2}'
        assert minimax_ai_task._extract_json(text) == '{"a": 1}'

    def test_extract_json_falls_back_to_literal(self):
        """Test fallback to literal when no fence present."""
        text = 'Response: {"a": 1}'
        assert minimax_ai_task._extract_json(text) == '{"a": 1}'

    def test_extract_json_returns_trimmed(self):
        """Test fallback returns stripped text when no JSON found."""
        text = "   hello world   "
        assert minimax_ai_task._extract_json(text) == "hello world"

    def test_format_scalar_schema_with_description(self):
        """Test scalar schema with description."""
        schema = {"type": "string", "description": "User name"}
        result = minimax_ai_task._format_scalar_schema(schema)
        assert "string" in result
        assert "User name" in result

    def test_format_scalar_schema_with_enum(self):
        """Test scalar schema with enum values."""
        schema = {"type": "string", "enum": ["a", "b", "c"]}
        result = minimax_ai_task._format_scalar_schema(schema)
        assert "one of" in result
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_format_array_schema_of_objects(self):
        """Test array schema with object items."""
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
            },
        }
        result = minimax_ai_task._format_array_schema(schema, 0)
        assert "id" in result
        assert "integer" in result

    def test_format_array_schema_of_primitives(self):
        """Test array schema with scalar items."""
        schema = {"type": "array", "items": {"type": "string"}}
        result = minimax_ai_task._format_array_schema(schema, 0)
        assert "string" in result

    def test_format_object_schema_required_field(self):
        """Test object schema marks required fields."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User name"},
            },
            "required": ["name"],
        }
        result = minimax_ai_task._format_object_schema(schema, 0)
        assert "name" in result
        assert "User name" in result
        assert "(required)" in result

    def test_format_object_schema_optional_field(self):
        """Test object schema handles optional fields."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User name"},
            },
            "required": [],
        }
        result = minimax_ai_task._format_object_schema(schema, 0)
        assert "name" in result
        assert "(required)" not in result

    def test_format_object_schema_nested_object(self):
        """Test object schema with nested object property."""
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            },
            "required": [],
        }
        result = minimax_ai_task._format_object_schema(schema, 0)
        assert "address" in result
        assert "city" in result

    def test_format_object_schema_array_property(self):
        """Test object schema with array property."""
        schema = {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        }
        result = minimax_ai_task._format_object_schema(schema, 0)
        assert "tags" in result
        assert "string" in result

    def test_openapi_schema_to_text_routes_to_object(self):
        """Test _openapi_schema_to_text routes object type."""
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
        }
        result = minimax_ai_task._openapi_schema_to_text(schema)
        assert "x" in result

    def test_openapi_schema_to_text_routes_to_array(self):
        """Test _openapi_schema_to_text routes array type."""
        schema = {"type": "array", "items": {"type": "string"}}
        result = minimax_ai_task._openapi_schema_to_text(schema)
        assert "string" in result

    def test_openapi_schema_to_text_routes_to_scalar(self):
        """Test _openapi_schema_to_text routes other types to scalar formatter."""
        schema = {"type": "string"}
        result = minimax_ai_task._openapi_schema_to_text(schema)
        assert "string" in result

    def test_openapi_schema_to_text_handles_non_dict(self):
        """Test _openapi_schema_to_text handles non-dict input."""
        result = minimax_ai_task._openapi_schema_to_text("not a dict")
        assert result == "not a dict"

    def test_schema_to_description_uses_generic_on_error(self, caplog):
        """Test _schema_to_description returns generic instruction on failure."""
        with patch(
            "custom_components.minimax.ai_task.convert",
            side_effect=Exception("bad schema"),
        ):
            result = minimax_ai_task._schema_to_description(vol.Schema({}))
        assert "Respond with ONLY" in result

    def test_schema_to_description_returns_text(self):
        """Test _schema_to_description returns text from convert."""
        schema = vol.Schema({vol.Required("x"): str})
        result = minimax_ai_task._schema_to_description(schema)
        assert "x" in result
        assert "string" in result

    def test_format_object_schema_property_with_enum(self):
        """Test object schema with a property that has enum values (line 81)."""
        schema = {
            "type": "object",
            "properties": {
                "color": {"type": "string", "enum": ["red", "green", "blue"]},
            },
            "required": ["color"],
        }
        result = minimax_ai_task._format_object_schema(schema, 0)
        assert "color" in result
        assert "one of" in result
        assert "red" in result
        assert "green" in result
        assert "blue" in result
        assert "(required)" in result


def _make_chat_log_with_assistant():
    """Create a chat log that has system + user + assistant content."""
    from homeassistant.components import conversation

    system_content = MagicMock()
    system_content.role = "system"
    system_content.content = "You are a helpful assistant."

    user_content = conversation.UserContent(content="First question", attachments=[])
    assistant_content = conversation.AssistantContent(
        agent_id="agent_001", content="First answer"
    )
    user_content2 = conversation.UserContent(content="Second question", attachments=[])

    log = MagicMock()
    log.content = [system_content, user_content, assistant_content, user_content2]
    log.conversation_id = "conv_002"

    def _add_user(content):
        log.content.append(content)

    log.async_add_user_content = MagicMock(side_effect=_add_user)
    log.async_add_assistant_content_without_tools = MagicMock()
    return log


def _make_chat_log_no_system():
    """Create a chat log with no system content (only user content)."""
    from homeassistant.components import conversation

    user_content = conversation.UserContent(content="Hello", attachments=[])

    log = MagicMock()
    log.content = [user_content]
    log.conversation_id = "conv_003"

    def _add_user(content):
        log.content.append(content)

    log.async_add_user_content = MagicMock(side_effect=_add_user)
    log.async_add_assistant_content_without_tools = MagicMock()
    return log


class TestGenerateDataChatLogVariants:
    """Test _async_generate_data with various chat_log configurations."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        from tests import create_mock_minimax_client

        return create_mock_minimax_client()

    @pytest.fixture
    def entity(self, mock_client):
        """Create an AI task entity."""
        entry = _make_config_entry()
        subentry = _make_subentry()
        return minimax_ai_task.MiniMaxAITaskEntity(entry, subentry, mock_client)

    @pytest.mark.asyncio
    async def test_assistant_content_in_chat_log(self, entity, mock_client):
        """Test that AssistantContent in chat_log is included in messages (lines 237-239)."""

        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Second question"
        task.structure = None
        task.attachments = []
        chat_log = _make_chat_log_with_assistant()

        mock_client.async_chat = AsyncMock(
            return_value={"success": True, "text": "Reply"}
        )

        await entity._async_generate_data(task, chat_log)

        call_kwargs = mock_client.async_chat.call_args.kwargs
        messages = call_kwargs["messages"]
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert assistant_msgs[0]["content"] == "First answer"

    @pytest.mark.asyncio
    async def test_no_system_content_with_structure(self, entity, mock_client):
        """Test structure added when no system content exists (line 257)."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Give me data"
        task.attachments = []
        task.structure = vol.Schema({vol.Required("value"): str})
        chat_log = _make_chat_log_no_system()

        mock_client.async_chat = AsyncMock(
            return_value={"success": True, "text": '{"value": "ok"}'}
        )

        await entity._async_generate_data(task, chat_log)

        call_kwargs = mock_client.async_chat.call_args.kwargs
        system_prompt = call_kwargs["system_prompt"]
        assert "CRITICAL" in system_prompt
        assert "respond with ONLY" in system_prompt
        assert not system_prompt.startswith("\n\n")

    @pytest.mark.asyncio
    async def test_json_parse_skips_empty_second_candidate(self, entity, mock_client):
        """Test that empty _extract_json candidate is skipped (line 313)."""
        task = MagicMock(spec=ai_task.GenDataTask)
        task.instructions = "Provide data"
        task.attachments = []
        task.structure = vol.Schema({vol.Required("x"): int})
        chat_log = _make_chat_log("Provide data")

        mock_client.async_chat = AsyncMock(
            return_value={"success": True, "text": "not parseable"}
        )

        with (
            patch(
                "custom_components.minimax.ai_task._extract_json",
                return_value="",
            ),
            pytest.raises(HomeAssistantError, match="Sorry, I had a problem"),
        ):
            await entity._async_generate_data(task, chat_log)

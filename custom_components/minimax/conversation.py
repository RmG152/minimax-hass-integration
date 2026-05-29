"""Conversation support for MiniMax."""

import logging
import re
import time
from typing import Any, Literal
import uuid

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent, llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import MiniMaxApiClient, MiniMaxApiClientError
from .const import (
    CONF_CHAT_MODEL,
    CONF_CONVERSATION_EXPIRY_MINUTES,
    CONF_CONVERSATION_MAX_TOKENS,
    CONF_CONVERSATION_TTS_ENABLED,
    CONF_MAX_CONVERSATIONS,
    CONF_MEMORY_ENABLED,
    CONF_MEMORY_EXPIRY_DAYS,
    CONF_MEMORY_MAX_COUNT,
    CONF_PROMPT,
    DEFAULT_CONVERSATION_EXPIRY_MINUTES,
    DEFAULT_CONVERSATION_MAX_TOKENS,
    DEFAULT_MAX_CONVERSATIONS,
    DEFAULT_MEMORY_ENABLED,
    DEFAULT_MEMORY_EXPIRY_DAYS,
    DEFAULT_MEMORY_MAX_COUNT,
    DEFAULT_MIN_MAX_TOKENS,
    DOMAIN,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
)
from .memory import MemoryStore

_LOGGER = logging.getLogger(__name__)

MAX_TOOL_CALLS = 10
_CHARS_PER_TOKEN = 4


def _get_exposed_entities(hass: HomeAssistant, assistant: str) -> dict[str, Any]:
    """Get exposed entities for the assistant."""
    return llm._get_exposed_entities(hass, assistant)  # noqa: SLF001


def _build_system_prompt(user_prompt: str, hass: HomeAssistant, agent_id: str) -> str:
    """Build system prompt with exposed entity state."""
    try:
        exposed = _get_exposed_entities(hass, agent_id)
        entities_info = ""

        if exposed and exposed.get("entities"):
            entities_info = (
                "\n\nStatic Context - Your Home Assistant devices and their states:\n"
            )
            for entity_data in exposed["entities"].values():
                entities_info += f"- {entity_data.get('name', entity_data.get('entity_id'))}: {entity_data.get('state', 'unknown')}\n"
        else:
            all_states = hass.states.async_all()
            if all_states:
                entities_info = "\n\nStatic Context - Your Home Assistant devices and their states:\n"
                for state in sorted(all_states, key=lambda s: s.entity_id):
                    if state.entity_id.startswith(
                        "automation."
                    ) or state.entity_id.startswith("scene."):
                        continue
                    entities_info += f"- {state.name}: {state.state}\n"

    except Exception as err:  # noqa: BLE001
        LOGGER.warning("Could not get exposed entities: %s", err)
        return user_prompt
    else:
        return f"{user_prompt}{entities_info}"


def _get_homeassistant_tools(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Get Home Assistant services as tools for MiniMax."""
    tools = []

    key_domains = [
        "homeassistant",
        "light",
        "switch",
        "climate",
        "fan",
        "cover",
        "lock",
        "alarm_control_panel",
        "media_player",
        "input_boolean",
        "automation",
        "script",
    ]

    try:
        services = hass.services.async_services()
        descriptions = {}
        for domain in services:
            if domain in key_domains:
                descriptions[domain] = {}
                for service_name, service_data in services[domain].items():
                    descriptions[domain][service_name] = {
                        "name": service_name,
                        "description": service_data.get("description", ""),
                        "fields": service_data.get("fields", {}),
                    }
    except Exception as err:  # noqa: BLE001
        LOGGER.warning("Could not get service descriptions: %s", err)
        return tools
    else:
        for domain, services in descriptions.items():
            if domain not in key_domains:
                continue

            for service_name, service_desc in services.items():
                if service_name.startswith("_"):
                    continue

                tool_name = f"{domain}.{service_name}"
                description = service_desc.get(
                    "name", service_desc.get("description", f"{domain} {service_name}")
                )

                properties = {}
                required = []
                fields = service_desc.get("fields", {})

                for field_name, field_desc in fields.items():
                    field_type = "string"
                    if field_desc.get("schema"):
                        field_type = "string"
                    elif field_desc.get("example"):
                        field_type = type(field_desc["example"]).__name__

                    properties[field_name] = {
                        "type": field_type,
                        "description": field_desc.get("description", field_name),
                    }
                    if field_desc.get("required"):
                        required.append(field_name)

                if "entity_id" not in properties:
                    properties["entity_id"] = {
                        "type": "string",
                        "description": "The entity ID to target (e.g., light.living_room)",
                    }

                tool = {
                    "name": tool_name,
                    "description": description,
                    "input_schema": {
                        "type": "object",
                        "properties": properties,
                    },
                }

                if required:
                    tool["input_schema"]["required"] = required

                tools.append(tool)

    LOGGER.debug("Generated %d Home Assistant tools", len(tools))
    return tools


def _estimate_tokens(text: str) -> int:
    """Estimate token count for text."""
    return len(text) // _CHARS_PER_TOKEN


def _trim_conversation_history(
    messages: list[dict[str, Any]], max_tokens: int
) -> list[dict[str, Any]]:
    """Trim conversation history to fit within token limit."""
    if not messages:
        return messages

    msg_tokens: list[tuple[dict[str, Any], int]] = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            text = "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            )
        else:
            text = str(content)
        token_count = _estimate_tokens(text)
        msg_tokens.append((msg, token_count))

    total_tokens = sum(t for _, t in msg_tokens)
    if total_tokens <= max_tokens:
        return messages

    trimmed = []
    accumulated = 0
    for msg, token_count in msg_tokens:
        if accumulated + token_count > max_tokens and trimmed:
            break
        trimmed.append(msg)
        accumulated += token_count

    return trimmed


async def _call_service(
    hass: HomeAssistant, domain: str, service: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Call a Home Assistant service."""
    try:
        result = await hass.services.async_call(
            domain,
            service,
            data,
            blocking=True,
            return_response=True,
        )
        LOGGER.debug("Service call %s.%s result: %s", domain, service, result)
    except Exception as err:  # noqa: BLE001
        LOGGER.error("Service call failed: %s", err)
        return {"success": False, "error": str(err)}
    else:
        return {"success": True, "result": result}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    client = config_entry.runtime_data

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue

        async_add_entities(
            [MiniMaxConversationEntity(config_entry, subentry, client)],
            config_subentry_id=subentry.subentry_id,
        )


class MiniMaxConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """MiniMax conversation agent."""

    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(
        self, entry: ConfigEntry, subentry: ConfigSubentry, client: MiniMaxApiClient
    ) -> None:
        """Initialize the agent."""
        self.entry = entry
        self.subentry = subentry
        self._client = client
        self._attr_name = subentry.title
        self._attr_unique_id = subentry.subentry_id
        self._tts_enabled = subentry.data.get(CONF_CONVERSATION_TTS_ENABLED, True)
        self._max_tokens = max(
            subentry.data.get(
                CONF_CONVERSATION_MAX_TOKENS, DEFAULT_CONVERSATION_MAX_TOKENS
            ),
            DEFAULT_MIN_MAX_TOKENS,
        )
        self._expiry_minutes = subentry.data.get(
            CONF_CONVERSATION_EXPIRY_MINUTES, DEFAULT_CONVERSATION_EXPIRY_MINUTES
        )
        self._max_conversations = subentry.data.get(
            CONF_MAX_CONVERSATIONS, DEFAULT_MAX_CONVERSATIONS
        )
        self._memory_enabled = subentry.data.get(
            CONF_MEMORY_ENABLED, DEFAULT_MEMORY_ENABLED
        )
        self._memory_store = MemoryStore(
            entry_id=entry.entry_id,
            max_count=subentry.data.get(
                CONF_MEMORY_MAX_COUNT, DEFAULT_MEMORY_MAX_COUNT
            ),
            expiry_days=subentry.data.get(
                CONF_MEMORY_EXPIRY_DAYS, DEFAULT_MEMORY_EXPIRY_DAYS
            ),
        )
        self._conversation_history: dict[str, tuple[list[dict[str, Any]], float]] = {}
        self._tools: list[dict[str, Any]] | None = None

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        _LOGGER.debug("Conversation entity added to hass, setting agent")
        await super().async_added_to_hass()
        if self._memory_enabled and self._memory_store:
            self._memory_store.set_hass(self.hass)
            await self._memory_store.async_load()
        conversation.async_set_agent(self.hass, self.entry, self)
        _LOGGER.info("MiniMax conversation agent registered: %s", self._attr_unique_id)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        _LOGGER.debug("Conversation entity removing from hass")
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    def _get_tools(self) -> list[dict[str, Any]]:
        """Get or cache tools."""
        if self._tools is None:
            self._tools = _get_homeassistant_tools(self.hass)
            if self._memory_enabled:
                self._tools.extend(self._get_memory_tools())
        return self._tools

    def _get_memory_tools(self) -> list[dict[str, Any]]:
        """Get memory-related tools for the agent."""
        return [
            {
                "name": "remember_user_fact",
                "description": "Save an important fact about the user that should be remembered for future conversations. Use this when the user tells you something about themselves, their preferences, habits, or anything they want you to remember.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "fact": {
                            "type": "string",
                            "description": "The fact to remember (e.g., 'User's name is John', 'User prefers 20°C in bedroom', 'User has a dog named Max')",
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional category: 'name', 'preference', 'habit', 'device', 'other'",
                        },
                    },
                    "required": ["fact"],
                },
            },
            {
                "name": "recall_user_facts",
                "description": "Retrieve all previously remembered facts about the user. Call this at the start of conversations to know the user's context.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "forget_user_fact",
                "description": "Remove a specific fact from memory. Use when user corrects information or wants something forgotten.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "fact": {
                            "type": "string",
                            "description": "The fact or keyword to forget",
                        },
                    },
                    "required": ["fact"],
                },
            },
            {
                "name": "forget_all_user_facts",
                "description": "Remove all stored facts from memory. Use when user wants to clear all learned information.",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]

    async def _execute_tool_calls(
        self, tool_calls: list[dict[str, Any]], messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute tool calls and return results."""
        results = []

        for tool_call in tool_calls[:MAX_TOOL_CALLS]:
            name = tool_call.get("name", "")
            args = tool_call.get("input", {})
            tool_use_id = tool_call.get("id", "")

            if not name:
                continue

            if name in (
                "remember_user_fact",
                "recall_user_facts",
                "forget_user_fact",
                "forget_all_user_facts",
            ):
                result = await self._execute_memory_tool(name, args)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": str(result),
                    }
                )
                continue

            if "." in name:
                domain, service = name.split(".", 1)
            else:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": f"Invalid tool name: {name}",
                    }
                )
                continue

            _LOGGER.debug("Executing tool call: %s with args: %s", name, args)
            result = await _call_service(self.hass, domain, service, args)

            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": str(result),
                }
            )

        return results

    async def _execute_memory_tool(self, name: str, args: dict[str, Any]) -> str:
        """Execute a memory-related tool call."""
        if not self._memory_store:
            return "Memory system not initialized"

        if name == "remember_user_fact":
            fact = args.get("fact", "")
            category = args.get("category", "other")
            if not fact:
                return "No fact provided to remember"
            memory_id = await self._memory_store.async_add_fact(fact, category)
            return f"Remembered: {fact} (ID: {memory_id[:8]}...)"

        if name == "recall_user_facts":
            facts = await self._memory_store.async_get_facts()
            if not facts:
                return "No memories stored yet."
            fact_list = []
            for f in facts:
                cat = f.get("category", "other")
                fact_list.append(f"- [{cat}] {f['fact']}")
            return "Remembered facts:\n" + "\n".join(fact_list)

        if name == "forget_user_fact":
            fact = args.get("fact", "")
            if not fact:
                return "No fact specified to forget"
            removed = await self._memory_store.async_remove_fact(fact)
            if removed:
                return f"Forgotten: {fact}"
            return f"Could not find memory matching: {fact}"

        if name == "forget_all_user_facts":
            count = await self._memory_store.async_get_memory_count()
            await self._memory_store.async_clear()
            return f"Cleared all {count} memories"

        return "Unknown memory command"

    async def _get_memory_section(self) -> str:
        """Get memory section for system prompt."""
        if not self._memory_store:
            return ""

        try:
            memories = await self._memory_store.async_get_facts()
            if not memories:
                return ""

            memory_lines = [
                "\n\n## Known User Facts:",
                *(f"- {m['fact']}" for m in memories),
            ]

        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Could not get memories for system prompt: %s", err)
            return ""
        else:
            return "\n".join(memory_lines)

    async def _chat_with_api(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Send chat request to MiniMax API via Anthropic SDK."""

        result = await self._client.async_chat(
            model=model,
            messages=messages,
            system_prompt=system_prompt,
            tools=tools or None,
        )

        if not result.get("success", False):
            error = result.get("error", "Unknown error")
            raise MiniMaxApiClientError(f"API error: {error}")

        content_blocks = result.get("content", [])
        has_tool_use = result.get("tool_calls", [])

        if has_tool_use:
            tool_calls = []
            text_parts = []

            text_parts = [
                block.get("text", "")
                for block in content_blocks
                if block.get("type") == "text"
            ]

            tool_calls = [
                {
                    "id": tc.get("id", ""),
                    "name": tc.get("name", ""),
                    "input": tc.get("input", {}),
                }
                for tc in result.get("tool_calls", [])
            ]

            if tool_calls:
                _LOGGER.debug("Tool calls returned: %d", len(tool_calls))
                tool_results = await self._execute_tool_calls(tool_calls, messages)

                messages.append(
                    {
                        "role": "assistant",
                        "content": content_blocks,
                    }
                )

                messages.extend(
                    {"role": "user", "content": [result_item]}
                    for result_item in tool_results
                )

                try:
                    return await self._chat_with_api(
                        system_prompt, messages, tools, model
                    )
                except Exception as tool_error:
                    if (
                        "tool id" in str(tool_error).lower()
                        and "not found" in str(tool_error).lower()
                    ):
                        _LOGGER.warning(
                            "Tool result ID mismatch, returning text response without tool results"
                        )
                        text = "\n".join(text_parts) if text_parts else ""
                        if not text:
                            text = "Jeg husker informationen, men der opstod en fejl ved bekræftelse."
                        return text, messages
                    raise

            text = "\n".join(text_parts) if text_parts else ""
            return text, messages
        text = result.get("text", "")
        return text, messages

    def _cleanup_expired_conversations(self) -> None:
        """Remove expired or oldest conversations to enforce limits."""
        cleaned = 0
        history_size = len(self._conversation_history)

        if self._expiry_minutes:
            now = time.time()
            expiry_seconds = float(self._expiry_minutes) * 60
            expired = [
                cid
                for cid, (_, timestamp) in self._conversation_history.items()
                if now - timestamp > expiry_seconds
            ]
            for cid in expired:
                del self._conversation_history[cid]
                cleaned += 1

        if len(self._conversation_history) > self._max_conversations:
            sorted_convs = sorted(
                self._conversation_history.items(), key=lambda x: x[1][1]
            )
            excess = len(self._conversation_history) - self._max_conversations
            for cid, _ in sorted_convs[:excess]:
                del self._conversation_history[cid]
                cleaned += 1

        if cleaned or history_size > 0:
            _LOGGER.debug(
                "Conversation history: %d conversations, cleaned %d",
                history_size,
                cleaned,
            )

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a conversation message."""
        user_content = user_input.text.strip() if user_input.text else ""
        _LOGGER.debug(
            "Processing conversation input (length=%d)",
            len(user_content),
        )

        if not user_content:
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech("Please say something.")
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id or "",
            )

        self._cleanup_expired_conversations()

        conversation_id = user_input.conversation_id
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            _LOGGER.debug("New conversation, generated ID: %s", conversation_id)

        existing_history, _ = self._conversation_history.get(conversation_id, ([], 0.0))
        trimmed_history = _trim_conversation_history(
            list(existing_history), self._max_tokens
        )

        user_prompt = self.subentry.data.get(
            CONF_PROMPT,
            "You are EVA, a friendly AI home assistant. Be helpful and concise.",
        )
        system_prompt = _build_system_prompt(user_prompt, self.hass, DOMAIN)
        if self._memory_enabled and self._memory_store:
            memory_section = await self._get_memory_section()
            if memory_section:
                system_prompt += memory_section
        model = self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)

        user_message = {
            "role": "user",
            "content": [{"type": "text", "text": user_input.text}],
        }

        messages = [user_message]

        tools = self._get_tools()
        _LOGGER.debug(
            "Using MiniMax API with model: %s, tools: %d, history length: %d",
            model,
            len(tools),
            len(trimmed_history),
        )
        try:
            response_text, _ = await self._chat_with_api(
                system_prompt, trimmed_history + messages, tools, model
            )

            assistant_message = {
                "role": "assistant",
                "content": response_text,
            }
            new_history = [*trimmed_history, user_message, assistant_message]
            self._conversation_history[conversation_id] = (new_history, time.time())
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Conversation error: %s", err)
            response_text = "Sorry, I had trouble answering that."

        response_text = re.sub(
            r"<think>.*?</think>",
            "",
            response_text,
            flags=re.DOTALL,
        )
        response_text = response_text.strip()

        if not response_text:
            response_text = "Beklager, jeg kunne ikke få svar."

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response_text)

        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=conversation_id,
        )

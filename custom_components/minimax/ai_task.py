"""AI Task support for MiniMax."""

import hashlib
import logging
import re
from typing import Any

import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from . import MiniMaxConfigEntry
from .api import MiniMaxApiClient
from .const import (
    ANTHROPIC_CHAT_TIMEOUT,
    CONF_CHAT_MODEL,
    CONF_RECOMMENDED,
    RECOMMENDED_AI_TASK_MAX_TOKENS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_IMAGE_MODEL,
)
from .entity import MiniMaxBaseEntity

ERROR_GETTING_RESPONSE = "Sorry, I had a problem getting a response from MiniMax."

_LOGGER = logging.getLogger(__name__)


def _schema_to_description(schema: vol.Schema) -> str:
    """Convert a voluptuous schema to a human-readable JSON description."""
    try:
        openapi_schema = convert(
            schema,
            custom_serializer=llm.selector_serializer,
        )
    except Exception:  # noqa: BLE001
        _LOGGER.warning(
            "Could not convert schema to OpenAPI, using generic instruction"
        )
        return "Respond with ONLY a valid JSON object."

    return _openapi_schema_to_text(openapi_schema)


def _format_object_schema(schema: dict[str, Any], indent: int) -> str:
    """Format an object-type schema into a text description."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines: list[str] = []
    prefix = "  " * indent

    if indent == 0:
        lines.append("{")

    for key, prop in properties.items():
        is_required = key in required
        prop_type = prop.get("type", "any") if isinstance(prop, dict) else "any"
        prop_desc = prop.get("description", "") if isinstance(prop, dict) else ""
        prop_enum = prop.get("enum") if isinstance(prop, dict) else None

        if prop_type == "object" and isinstance(prop, dict):
            nested = _openapi_schema_to_text(prop, indent + 1)
            line = f'{prefix}  "{key}": {nested}'
        elif prop_type == "array" and isinstance(prop, dict):
            items = prop.get("items", {})
            item_type = items.get("type", "any") if isinstance(items, dict) else "any"
            line = f'{prefix}  "{key}": [<{item_type}>]'
        else:
            type_hint = prop_type
            if prop_enum:
                type_hint = (
                    f"{prop_type} (one of: {', '.join(str(e) for e in prop_enum)})"
                )
            line = f'{prefix}  "{key}": <{type_hint}>'

        if prop_desc:
            line += f" - {prop_desc}"
        if is_required:
            line += " (required)"

        lines.append(line)

    if indent == 0:
        lines.append("}")

    return "\n".join(lines)


def _format_array_schema(schema: dict[str, Any], indent: int) -> str:
    """Format an array-type schema into a text description."""
    items = schema.get("items", {})
    if isinstance(items, dict) and items.get("type") == "object":
        nested = _openapi_schema_to_text(items, indent)
        return f"[{nested}]"
    item_type = items.get("type", "any") if isinstance(items, dict) else "any"
    return f"[<array of {item_type}>]"


def _format_scalar_schema(schema: dict[str, Any]) -> str:
    """Format a scalar-type schema into a text description."""
    desc = schema.get("description", "")
    enum = schema.get("enum")
    schema_type = schema.get("type", "any")
    if enum:
        type_hint = f"{schema_type} (one of: {', '.join(str(e) for e in enum)})"
    else:
        type_hint = schema_type
    line = f"<{type_hint}>"
    if desc:
        line += f" - {desc}"
    return line


def _openapi_schema_to_text(schema: dict[str, Any], indent: int = 0) -> str:
    """Recursively convert an OpenAPI schema dict to a text description."""
    if not isinstance(schema, dict):
        return str(schema)
    schema_type = schema.get("type", "object")
    if schema_type == "object":
        return _format_object_schema(schema, indent)
    if schema_type == "array":
        return _format_array_schema(schema, indent)
    return _format_scalar_schema(schema)


def _raise_parse_error() -> None:
    """Raise parse error."""
    raise HomeAssistantError(ERROR_GETTING_RESPONSE)


def _extract_fenced_code(text: str) -> str | None:
    """Extract content from a markdown fenced code block."""
    match = re.search(r"```(?:json)?(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else None


def _extract_json_literal(text: str) -> str | None:
    """Extract a JSON object or array literal from text."""
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    return match.group(1).strip() if match else None


def _extract_json(text: str) -> str:
    """Extract JSON from markdown code blocks or raw text."""
    extracted = _extract_fenced_code(text)
    if extracted:
        return extracted
    extracted = _extract_json_literal(text)
    if extracted:
        return extracted
    return text.strip()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    client = config_entry.runtime_data

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [MiniMaxAITaskEntity(config_entry, subentry, client)],
            config_subentry_id=subentry.subentry_id,
        )


class MiniMaxAITaskEntity(MiniMaxBaseEntity, ai_task.AITaskEntity):
    """MiniMax AI Task entity."""

    _attr_supported_features = (
        ai_task.AITaskEntityFeature.GENERATE_DATA
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )

    def __init__(
        self,
        entry: MiniMaxConfigEntry,
        subentry: ConfigSubentry,
        client: MiniMaxApiClient,
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry, client)

        if subentry.data.get(CONF_RECOMMENDED) or "-image" in subentry.data.get(
            CONF_CHAT_MODEL, ""
        ):
            self._attr_supported_features |= ai_task.AITaskEntityFeature.GENERATE_IMAGE

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        options = self.subentry.data
        model = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)

        _LOGGER.debug(
            "AI task generate_data: model=%s, has_structure=%s, instructions=%s",
            model,
            bool(task.structure),
            task.instructions[:100] if task.instructions else "",
        )

        try:
            chat_log.async_add_user_content(
                conversation.UserContent(
                    content=task.instructions,
                    attachments=task.attachments,
                )
            )

            messages = []
            for content in chat_log.content[1:]:
                if isinstance(content, conversation.UserContent):
                    msg_content = content.content or ""
                    messages.append({"role": "user", "content": msg_content})
                elif isinstance(content, conversation.AssistantContent):
                    msg_content = content.content or ""
                    messages.append({"role": "assistant", "content": msg_content})

            system_prompt = ""
            if chat_log.content and chat_log.content[0].role == "system":
                system_prompt = chat_log.content[0].content or ""

            if task.structure:
                schema_description = _schema_to_description(task.structure)
                json_instruction = (
                    "\n\nCRITICAL: You must respond with ONLY a valid JSON object matching this exact schema. "
                    "Do not include any markdown formatting, explanations, or other text. "
                    "Your entire response must be parseable as JSON. "
                    "Do not add any fields that are not listed below, and do not omit any required fields.\n\n"
                    f"{schema_description}"
                )
                if system_prompt:
                    system_prompt += json_instruction
                else:
                    system_prompt = json_instruction.lstrip()
                _LOGGER.debug(
                    "AI task: added JSON schema instruction to system prompt, schema:\n%s",
                    schema_description,
                )

            _LOGGER.debug(
                "AI task: calling async_chat with system_prompt=%s, messages_count=%d",
                bool(system_prompt),
                len(messages),
            )

            result = await self._client.async_chat(
                model=model,
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=RECOMMENDED_AI_TASK_MAX_TOKENS,
                timeout=ANTHROPIC_CHAT_TIMEOUT,
            )

            if not result.get("success", False):
                msg = (
                    f"{ERROR_GETTING_RESPONSE}: {result.get('error', 'Unknown error')}"
                )
                raise HomeAssistantError(msg)  # noqa: TRY301

            text = result.get("text", "")
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

            _LOGGER.debug(
                "AI task: raw response length=%d",
                len(text),
            )

            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(
                    agent_id=self.entity_id,
                    content=text,
                )
            )

            if not task.structure:
                return ai_task.GenDataTaskResult(
                    conversation_id=chat_log.conversation_id,
                    data=text,
                )

            if not text:
                msg = "MiniMax returned an empty response, expected structured data"
                raise HomeAssistantError(msg)  # noqa: TRY301

            data = None
            parse_errors = []
            candidates = [text, _extract_json(text)]
            for attempt, candidate in enumerate(candidates, 1):
                if not candidate:
                    continue
                _LOGGER.debug(
                    "AI task: JSON parse attempt %d, candidate_length=%d, candidate=%s",
                    attempt,
                    len(candidate),
                    candidate[:300],
                )
                try:
                    data = json_loads(candidate)
                    _LOGGER.debug(
                        "AI task: JSON parsed successfully on attempt %d", attempt
                    )
                    break
                except (ValueError, TypeError) as err:
                    parse_errors.append(f"Attempt {attempt}: {err}")
                    if attempt == len(candidates):
                        _LOGGER.error(
                            "AI task: Failed to parse JSON. Errors: %s. "
                            "Response length=%d, hash=%s, snippet=%s",
                            "; ".join(parse_errors),
                            len(text),
                            hashlib.sha256(text.encode()).hexdigest(),
                            text[:200],
                        )

            if data is None:
                _raise_parse_error()

            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=data,
            )

        except HomeAssistantError:
            raise
        except Exception as err:
            _LOGGER.error("Error generating data: %s", err)
            raise HomeAssistantError(ERROR_GETTING_RESPONSE) from err

    async def _async_generate_image(
        self,
        task: ai_task.GenImageTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenImageTaskResult:
        """Handle a generate image task."""
        options = self.subentry.data
        model = options.get(CONF_CHAT_MODEL, RECOMMENDED_IMAGE_MODEL)

        try:
            prompt = task.instructions
            if task.attachments:
                prompt = f"{task.instructions}\n\n[Image attachments provided]"

            image_data = await self._client.async_image_generation(
                prompt=prompt,
                model=model,
                aspect_ratio="1:1",
            )

            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(
                    agent_id=self.entity_id,
                    content="Generated image for: " + task.instructions,
                )
            )

            return ai_task.GenImageTaskResult(
                image_data=image_data,
                conversation_id=chat_log.conversation_id,
                mime_type="image/png",
                model=model,
            )

        except Exception as err:
            _LOGGER.error("Error generating image: %s", err)
            raise HomeAssistantError(f"Error generating image: {err}") from err

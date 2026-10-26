"""AI Task support for MiniMax."""

import hashlib
import logging
import re
from typing import Any

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm, selector
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from . import MiniMaxConfigEntry
from .api import MiniMaxApiClient
from .const import (
    CONF_CHAT_MODEL,
    CONF_RECOMMENDED,
    RECOMMENDED_AI_TASK_MAX_TOKENS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_IMAGE_MODEL,
)
from .entity import MiniMaxBaseEntity

ERROR_GETTING_RESPONSE = "Sorry, I had a problem getting a response from MiniMax."

_LOGGER = logging.getLogger(__name__)


def _schema_to_description(schema: Any) -> str:
    """Convert a voluptuous or probatio schema to a human-readable JSON description."""
    try:
        openapi_schema = _schema_to_openapi(schema)
    except Exception:  # noqa: BLE001
        _LOGGER.warning(
            "Could not convert schema to OpenAPI, using generic instruction"
        )
        return "Respond with ONLY a valid JSON object."

    return _openapi_schema_to_text(openapi_schema)


def _schema_to_openapi(schema: Any) -> dict[str, Any]:
    """Convert a voluptuous or probatio schema into an OpenAPI-style dictionary."""
    if isinstance(schema, dict):
        return _object_to_openapi(schema)

    inner = getattr(schema, "schema", None)
    if isinstance(inner, dict):
        return _object_to_openapi(inner)

    return _value_to_openapi(schema)


def _object_to_openapi(mapping: dict[str, Any]) -> dict[str, Any]:
    """Convert a schema mapping into an OpenAPI-style object schema."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for key, value in mapping.items():
        name, description, is_required = _describe_key(key)
        prop = _value_to_openapi(value)
        if description:
            prop["description"] = description
        properties[name] = prop
        if is_required:
            required.append(name)

    result: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


def _describe_key(key: Any) -> tuple[str, str | None, bool]:
    """Return the property name, description and required flag for a schema key."""
    if not isinstance(key, (str, int, float, bool)):
        marker_schema = getattr(key, "schema", None)
        if marker_schema is not None:
            name = (
                marker_schema if isinstance(marker_schema, str) else str(marker_schema)
            )
            description = getattr(key, "description", None)
            return name, description, type(key).__name__ == "Required"

    return str(key), None, False


def _value_to_openapi(value: Any) -> dict[str, Any]:
    """Convert a single schema value into an OpenAPI-style dictionary."""
    if isinstance(value, dict):
        return _object_to_openapi(value)

    if isinstance(value, (list, tuple)):
        return {"type": "array", "items": _items_to_openapi(value)}

    if isinstance(value, selector.Selector):
        return _selector_to_openapi(value)

    inner = getattr(value, "schema", None)
    if isinstance(inner, dict):
        return _object_to_openapi(inner)
    if isinstance(inner, (list, tuple)):
        return {"type": "array", "items": _items_to_openapi(inner)}

    validator = _validator_to_openapi(value)
    if validator is not None:
        return validator

    if value is None:
        return {"type": "null"}

    json_type = _json_type(value)
    if json_type is not None:
        return {"type": json_type}

    return {"type": "any"}


def _items_to_openapi(values: Any) -> dict[str, Any]:
    """Convert the items of a sequence schema into an OpenAPI-style dictionary."""
    if not values:
        return {"type": "any"}
    return _value_to_openapi(values[0])


def _selector_to_openapi(value: Any) -> dict[str, Any]:
    """Convert a Home Assistant selector into an OpenAPI-style dictionary."""
    try:
        converted = llm.selector_serializer(value)
    except Exception:  # noqa: BLE001
        converted = None

    if isinstance(converted, dict):
        return converted
    return {"type": "string"}


def _validator_to_openapi(value: Any) -> dict[str, Any] | None:
    """Convert a voluptuous or probatio validator into an OpenAPI-style dictionary."""
    validators = getattr(value, "validators", None)
    if validators:
        return _validators_to_openapi(validators)

    coerced = getattr(value, "type", None)
    if coerced is not None:
        return _value_to_openapi(coerced)

    container = getattr(value, "container", None)
    if container is not None:
        return _container_to_openapi(container)

    return _range_to_openapi(value)


def _validators_to_openapi(validators: Any) -> dict[str, Any]:
    """Convert a list of validators into an OpenAPI-style dictionary."""
    for validator in validators:
        converted = _value_to_openapi(validator)
        if converted.get("type") != "any":
            return converted
    return {"type": "any"}


def _container_to_openapi(container: Any) -> dict[str, Any]:
    """Convert a validator container (a set of enum options) into an OpenAPI-style dictionary."""
    options = list(container)
    if not options:
        return {"type": "any"}
    return {"type": _json_type_of_value(options[0]) or "any", "enum": options}


def _range_to_openapi(value: Any) -> dict[str, Any] | None:
    """Convert a numeric range validator into an OpenAPI-style dictionary."""
    minimum = getattr(value, "min", None)
    maximum = getattr(value, "max", None)
    if minimum is None and maximum is None:
        return None

    result: dict[str, Any] = {"type": "number"}
    if minimum is not None:
        result["minimum"] = minimum
    if maximum is not None:
        result["maximum"] = maximum
    return result


def _json_type(value: Any) -> str | None:
    """Return the JSON schema type for a Python type."""
    if value is bool:
        return "boolean"
    if value is int:
        return "integer"
    if value is float:
        return "number"
    if value is str:
        return "string"
    if value is dict:
        return "object"
    if value is list or value is tuple or value is set or value is frozenset:
        return "array"
    return None


def _json_type_of_value(value: Any) -> str | None:
    """Return the JSON schema type for a Python value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "array"
    return None


def _format_object_schema(schema: dict[str, Any], indent: int) -> str:
    """Format an object-type schema into a text description."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines: list[str] = []

    if indent == 0:
        lines.append("{")

    for key, prop in properties.items():
        lines.append(_format_property_line(key, prop, key in required, indent))

    if indent == 0:
        lines.append("}")

    return "\n".join(lines)


def _format_property_line(key: str, prop: Any, is_required: bool, indent: int) -> str:
    """Format a single property of an object schema as a text line."""
    prefix = "  " * indent
    prop_dict = prop if isinstance(prop, dict) else {}
    prop_type = prop_dict.get("type", "any")
    prop_desc = prop_dict.get("description", "")
    prop_enum = prop_dict.get("enum")

    if prop_type == "object":
        nested = _openapi_schema_to_text(prop_dict, indent + 1)
        line = f'{prefix}  "{key}": {nested}'
    elif prop_type == "array":
        items = prop_dict.get("items", {})
        item_type = items.get("type", "any") if isinstance(items, dict) else "any"
        line = f'{prefix}  "{key}": [<{item_type}>]'
    else:
        type_hint = prop_type
        if prop_enum:
            type_hint = f"{prop_type} (one of: {', '.join(str(e) for e in prop_enum)})"
        line = f'{prefix}  "{key}": <{type_hint}>'

    if prop_desc:
        line += f" - {prop_desc}"
    if is_required:
        line += " (required)"

    return line


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


def _build_chat_messages(chat_log: conversation.ChatLog) -> list[dict[str, Any]]:
    """Build the API message list from a conversation chat log."""
    messages: list[dict[str, Any]] = []
    for content in chat_log.content[1:]:
        if isinstance(content, conversation.UserContent):
            messages.append({"role": "user", "content": content.content or ""})
        elif isinstance(content, conversation.AssistantContent):
            messages.append({"role": "assistant", "content": content.content or ""})
    return messages


def _extract_system_prompt(chat_log: conversation.ChatLog) -> str:
    """Return the system prompt of a conversation chat log, if it has one."""
    if chat_log.content and chat_log.content[0].role == "system":
        return chat_log.content[0].content or ""
    return ""


def _append_schema_instruction(system_prompt: str, structure: Any) -> str:
    """Return the system prompt extended with the JSON schema instruction."""
    schema_description = _schema_to_description(structure)
    json_instruction = (
        "\n\nCRITICAL: You must respond with ONLY a valid JSON object matching this exact schema. "
        "Do not include any markdown formatting, explanations, or other text. "
        "Your entire response must be parseable as JSON. "
        "Do not add any fields that are not listed below, and do not omit any required fields.\n\n"
        f"{schema_description}"
    )
    if system_prompt:
        return system_prompt + json_instruction
    return json_instruction.lstrip()


def _parse_json_response(text: str) -> Any:
    """Parse the JSON payload of a structured AI task response."""
    if not text:
        msg = "MiniMax returned an empty response, expected structured data"
        raise HomeAssistantError(msg)

    parse_errors = []
    candidates = [text, _extract_json(text)]
    data = None
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
            _LOGGER.debug("AI task: JSON parsed successfully on attempt %d", attempt)
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

    return data


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

            messages = _build_chat_messages(chat_log)
            system_prompt = _extract_system_prompt(chat_log)

            if task.structure:
                system_prompt = _append_schema_instruction(
                    system_prompt, task.structure
                )
                _LOGGER.debug(
                    "AI task: added JSON schema instruction to system prompt, schema:\n%s",
                    _schema_to_description(task.structure),
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

            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=_parse_json_response(text),
            )

        except HomeAssistantError:
            raise
        except Exception as err:
            _LOGGER.exception("Error generating data")
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
            _LOGGER.exception("Error generating image")
            raise HomeAssistantError(f"Error generating image: {err}") from err

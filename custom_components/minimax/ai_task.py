"""AI Task support for MiniMax."""

import logging
import re
from typing import TYPE_CHECKING

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from .api import MiniMaxApiClient
from .const import (
    AI_TASK_TIMEOUT,
    CONF_CHAT_MODEL,
    CONF_RECOMMENDED,
    RECOMMENDED_AI_TASK_MAX_TOKENS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_IMAGE_MODEL,
)

if TYPE_CHECKING:
    type MiniMaxConfigEntry = ConfigEntry[MiniMaxApiClient]

ERROR_GETTING_RESPONSE = "Sorry, I had a problem getting a response from MiniMax."

_LOGGER = logging.getLogger(__name__)


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


class MiniMaxAITaskEntity(ai_task.AITaskEntity):
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
        self.entry = entry
        self.subentry = subentry
        self._client = client
        self._attr_name = subentry.title
        self._attr_unique_id = subentry.subentry_id

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

            result = await self._client.async_chat(
                model=model,
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=RECOMMENDED_AI_TASK_MAX_TOKENS,
                timeout=AI_TASK_TIMEOUT,
            )

            if not result.get("success", False):
                msg = (
                    f"{ERROR_GETTING_RESPONSE}: {result.get('error', 'Unknown error')}"
                )
                raise HomeAssistantError(msg)  # noqa: TRY301

            text = result.get("text", "")
            text = re.sub(
                r"<think>.*?</think>", "", text, flags=re.DOTALL
            ).strip()

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
                raise HomeAssistantError(
                    "MiniMax returned an empty response, expected structured data"
                )

            try:
                data = json_loads(text)
            except Exception as err:
                _LOGGER.error(
                    "Failed to parse JSON response: %s. Response: %s",
                    err,
                    text[:200],
                )
                raise HomeAssistantError(ERROR_GETTING_RESPONSE) from err

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

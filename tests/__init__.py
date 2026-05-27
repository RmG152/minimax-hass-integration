"""Tests for the MiniMax integration."""

import contextlib
from typing import Any
from unittest.mock import AsyncMock

from aioresponses import aioresponses
from pytest_homeassistant_custom_component.common import MockConfigEntry
import respx

from custom_components.minimax.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

TEST_API_KEY = "test_api_key_12345"
TEST_CONFIG_ENTRY_ID = "minimax_test_entry_001"

CHAT_RESPONSE_SUCCESS = {
    "success": True,
    "text": "Hello! How can I help you?",
    "tool_calls": [],
    "stop_reason": "end_turn",
}

CHAT_RESPONSE_WITH_TOOL_CALL = {
    "success": True,
    "text": "",
    "tool_calls": [
        {
            "id": "toolu_123",
            "name": "light.turn_on",
            "input": {"entity_id": "light.living_room"},
        }
    ],
    "content": [{"type": "text", "text": "Turning on the light."}],
    "stop_reason": "end_turn",
}

TTS_RESPONSE_BYTES = b"fake_audio_data"
STT_RESPONSE_TEXT = "This is transcribed text."


def create_mock_minimax_client() -> AsyncMock:
    """Create mock MiniMax API client."""
    mock_client = AsyncMock()
    mock_client.async_verify_connection = AsyncMock(return_value=True)
    mock_client.async_chat = AsyncMock(return_value=CHAT_RESPONSE_SUCCESS.copy())
    mock_client.async_tts = AsyncMock(return_value=TTS_RESPONSE_BYTES)
    mock_client.async_stt = AsyncMock(return_value=STT_RESPONSE_TEXT)
    return mock_client


def create_mock_minimax_config_entry(
    hass: HomeAssistant,
    data: dict[str, Any] | None = None,
    entry_id: str | None = TEST_CONFIG_ENTRY_ID,
) -> MockConfigEntry:
    """Create a mock MiniMax config entry."""
    config_entry: MockConfigEntry = MockConfigEntry(
        entry_id=entry_id,
        domain=DOMAIN,
        data=data or {CONF_API_KEY: TEST_API_KEY},
        title="MiniMax",
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def setup_mock_minimax_config_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry | None = None,
    client: AsyncMock | None = None,
) -> ConfigEntry:
    """Add a mock MiniMax config entry to hass."""
    config_entry = config_entry or create_mock_minimax_config_entry(hass)
    client = client or create_mock_minimax_client()

    with (
        respx.mock,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry


@contextlib.contextmanager
def mock_minimax_api(
    chat_response: dict[str, Any] | None = None,
    tts_response: bytes | None = None,
    stt_response: str | None = None,
    chat_side_effect: Exception | None = None,
    tts_side_effect: Exception | None = None,
    stt_side_effect: Exception | None = None,
):
    """Context manager to mock MiniMax API calls using respx."""
    chat_response = chat_response or CHAT_RESPONSE_SUCCESS.copy()
    tts_response = tts_response or TTS_RESPONSE_BYTES
    stt_response = stt_response or STT_RESPONSE_TEXT

    with respx.mock(base_url="https://api.minimax.io") as respx_mock:
        chat_route = respx_mock.post("/anthropic/v1/messages").mock(
            return_value=aioresponses.JSONResponse(
                status=200,
                body={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": chat_response.get("text", "Hello!")}
                    ],
                    "model": "MiniMax-M2.7",
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                },
            )
        )
        if chat_side_effect:
            chat_route.mock(side_effect=chat_side_effect)

        tts_route = respx_mock.post("/v1/t2a_v2").mock(
            return_value=aioresponses.JSONResponse(
                status=200,
                body={
                    "model": "speech-2.8-hd",
                    "data": {"audio": tts_response.hex()},
                },
            )
        )
        if tts_side_effect:
            tts_route.mock(side_effect=tts_side_effect)

        stt_route = respx_mock.post("/v1/audio/transcription").mock(
            return_value=aioresponses.JSONResponse(
                status=200,
                body={"text": stt_response, "code": 0, "msg": "success"},
            )
        )
        if stt_side_effect:
            stt_route.mock(side_effect=stt_side_effect)

        yield respx_mock

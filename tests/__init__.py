"""Tests for the MiniMax integration."""

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState


class MockConfigEntry:
    """Simple mock for Home Assistant ConfigEntry."""

    def __init__(
        self,
        *,
        entry_id: str = "test_entry",
        domain: str = "minimax",
        data: dict[str, Any] | None = None,
        title: str = "MiniMax",
        version: int = 1,
        minor_version: int = 1,
        subentries: dict | None = None,
    ) -> None:
        """Initialize the mock config entry."""
        self.entry_id = entry_id
        self.domain = domain
        self.data = data or {}
        self.title = title
        self.version = version
        self.minor_version = minor_version
        self.subentries = subentries or {}
        self.options: dict[str, Any] = {}
        self.runtime_data: Any = None
        self.state = ConfigEntryState.LOADED
        self._on_unload: list = []

    def add_to_hass(self, hass: Any) -> None:
        """Add this entry to hass."""
        hass.config_entries._entries[self.entry_id] = self

    def add_update_listener(self, listener):
        """Register update listener and return unsubscribe callable."""
        self._update_listeners = getattr(self, "_update_listeners", [])
        self._update_listeners.append(listener)
        return lambda: self._update_listeners.remove(listener)

    def async_on_unload(self, callback) -> None:
        """Register callback for unload."""
        self._on_unload.append(callback)


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
    "stop_reason": "end_turn",
}

TTS_RESPONSE_BYTES = b"fake_audio_data"
STT_RESPONSE_TEXT = "This is transcribed text."
IMAGE_RESPONSE_BYTES = b"fake_image_data"


def create_mock_minimax_client() -> AsyncMock:
    """Create a mock MiniMax API client."""
    return AsyncMock(
        async_verify_connection=AsyncMock(return_value=True),
        async_chat=AsyncMock(return_value=CHAT_RESPONSE_SUCCESS.copy()),
        async_tts=AsyncMock(return_value=TTS_RESPONSE_BYTES),
        async_stt=AsyncMock(return_value=STT_RESPONSE_TEXT),
        async_image_generation=AsyncMock(return_value=IMAGE_RESPONSE_BYTES),
    )


def create_mock_minimax_config_entry(
    hass: Any,
    data: dict[str, Any] | None = None,
    entry_id: str | None = TEST_CONFIG_ENTRY_ID,
) -> MockConfigEntry:
    """Create and add a mock MiniMax config entry to hass."""
    config_entry = MockConfigEntry(
        entry_id=entry_id or TEST_CONFIG_ENTRY_ID,
        domain="minimax",
        data=data or {CONF_API_KEY: TEST_API_KEY},
        title="MiniMax",
    )
    config_entry.add_to_hass(hass)
    return config_entry


# Must import after MockConfigEntry is defined
from custom_components.minimax.const import CONF_API_KEY  # noqa: E402

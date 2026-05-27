"""Pytest configuration for MiniMax integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.plugins import (  # noqa: F401
    enable_custom_integrations,
)

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(name="skip_notifications")
def skip_notifications_fixture() -> Generator:
    """Skip notification calls."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield


@pytest.fixture(autouse=True)
def minimax_fixture(
    socket_enabled: Any,
    skip_notifications: Any,
    enable_custom_integrations: Any,  # noqa: F811
    hass: Any,
) -> None:
    """Automatically use an ordered combination of fixtures."""


@pytest.fixture
def mock_server_response():
    """Configure mock server responses."""
    return {
        "/v1/text/chatcompletion_v2": {
            "id": "chatcmpl-123",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help you?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        },
        "/v1/audio/t2a_v2": {
            "id": "tts-123",
            "choices": [{"finish_reason": "stop", "index": 0}],
            "data": "Zmxha2VfYXVkaW9fZGF0YQ==",
        },
        "/v1/audio/transcription": {
            "text": "This is transcribed text.",
            "code": 0,
            "msg": "success",
        },
    }

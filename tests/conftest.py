"""Pytest configuration for MiniMax integration tests."""

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock haffmpeg (HA optional dependency not available on Windows)
# Must be done before any import that triggers homeassistant.components.ffmpeg
for _mod_name in ["haffmpeg", "haffmpeg.core", "haffmpeg.tools"]:
    _m = types.ModuleType(_mod_name)
    _m.__package__ = _mod_name
    if _mod_name == "haffmpeg":
        _m.__path__ = []
    sys.modules[_mod_name] = _m

sys.modules["haffmpeg.core"].HAFFmpeg = MagicMock
sys.modules["haffmpeg.tools"].IMAGE_JPEG = "image_jpeg"
sys.modules["haffmpeg.tools"].FFVersion = MagicMock
sys.modules["haffmpeg.tools"].ImageFrame = MagicMock

# Mock turbojpeg (HA optional dependency not available on Windows)
# Required by homeassistant.components.camera which ai_task imports
_turbojpeg = types.ModuleType("turbojpeg")
_turbojpeg.TurboJPEG = MagicMock
_turbojpeg.TJCS_RGB = 0
_turbojpeg.TJCS_BGR = 1
_turbojpeg.TJPF_BGR = 0
_turbojpeg.TJPF_RGB = 1
sys.modules["turbojpeg"] = _turbojpeg


@pytest.fixture(name="skip_notifications")
def skip_notifications_fixture():
    """Skip notification calls."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield


@pytest.fixture(autouse=True)
def auto_patch_clientsession():
    """Auto-patch async_get_clientsession to avoid deep HA internals."""
    with (
        patch(
            "custom_components.minimax.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.minimax.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
    ):
        yield


@pytest.fixture
def hass():
    """Create a minimal mock HomeAssistant for testing."""
    hass = MagicMock()

    hass.data = {}
    hass.config = MagicMock()
    hass.config.config_dir = "/config"
    hass.states = MagicMock()
    hass.states.async_all = MagicMock(return_value=[])
    hass.services = MagicMock()
    hass.services.async_services = MagicMock(return_value={})
    hass.services.async_call = AsyncMock(return_value={"success": True, "result": "ok"})
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()

    # Mock config_entries with flow support
    config_entries = MagicMock()
    config_entries._entries = {}
    config_entries.flow = MagicMock()
    config_entries.flow.async_init = AsyncMock()
    config_entries.flow.async_configure = AsyncMock()
    config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    config_entries.async_unload_platforms = AsyncMock(return_value=True)
    config_entries.async_reload = AsyncMock(return_value=True)

    def _async_entries(domain, include_ignore=True):
        return [e for e in config_entries._entries.values() if e.domain == domain]

    config_entries.async_entries = _async_entries
    config_entries.async_get_known_entry = lambda entry_id: config_entries._entries.get(
        entry_id
    )
    hass.config_entries = config_entries

    hass.async_block_till_done = AsyncMock()

    return hass

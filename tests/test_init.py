"""Tests for MiniMax integration init."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.minimax import async_setup_entry, async_unload_entry
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady


class TestAsyncSetupEntry:
    """Test async_setup_entry."""

    async def test_setup_entry_success(self, hass):
        """Test successful setup of entry."""
        from tests import create_mock_minimax_client, create_mock_minimax_config_entry

        config_entry = create_mock_minimax_config_entry(hass)
        mock_client = create_mock_minimax_client()

        with patch("custom_components.minimax.MiniMaxApiClient", return_value=mock_client):
            result = await async_setup_entry(hass, config_entry)

        assert result is True
        assert config_entry.runtime_data is mock_client
        hass.config_entries.async_forward_entry_setups.assert_called_once()

    async def test_setup_entry_creates_client_with_api_key(self, hass):
        """Test setup_entry creates client with correct API key."""
        from tests import create_mock_minimax_config_entry

        config_entry = create_mock_minimax_config_entry(hass)

        with patch("custom_components.minimax.MiniMaxApiClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.async_verify_connection = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_instance

            await async_setup_entry(hass, config_entry)

            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs["api_key"] == config_entry.data["api_key"]

    async def test_setup_entry_auth_failed(self, hass):
        """Test setup_entry raises ConfigEntryAuthFailed."""
        from tests import create_mock_minimax_config_entry

        config_entry = create_mock_minimax_config_entry(hass)

        with patch("custom_components.minimax.MiniMaxApiClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.async_verify_connection = AsyncMock(
                side_effect=Exception("401 Unauthorized")
            )
            mock_client_class.return_value = mock_instance

            with pytest.raises(ConfigEntryAuthFailed):
                await async_setup_entry(hass, config_entry)

    async def test_setup_entry_not_ready(self, hass):
        """Test setup_entry raises ConfigEntryNotReady."""
        from tests import create_mock_minimax_config_entry

        config_entry = create_mock_minimax_config_entry(hass)

        with patch("custom_components.minimax.MiniMaxApiClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.async_verify_connection = AsyncMock(
                side_effect=Exception("Timeout connecting to MiniMax API")
            )
            mock_client_class.return_value = mock_instance

            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, config_entry)

    async def test_setup_entry_auth_from_error_string(self, hass):
        """Test setup_entry detects auth failure from error message."""
        from tests import create_mock_minimax_config_entry

        config_entry = create_mock_minimax_config_entry(hass)

        with patch("custom_components.minimax.MiniMaxApiClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.async_verify_connection = AsyncMock(
                side_effect=Exception("authentication failed: bad key")
            )
            mock_client_class.return_value = mock_instance

            with pytest.raises(ConfigEntryAuthFailed):
                await async_setup_entry(hass, config_entry)


class TestAsyncUnloadEntry:
    """Test async_unload_entry."""

    async def test_unload_entry_success(self, hass):
        """Test successful unload of entry."""
        from tests import create_mock_minimax_client, create_mock_minimax_config_entry

        config_entry = create_mock_minimax_config_entry(hass)
        mock_client = create_mock_minimax_client()

        with patch("custom_components.minimax.MiniMaxApiClient", return_value=mock_client):
            await async_setup_entry(hass, config_entry)

        result = await async_unload_entry(hass, config_entry)

        assert result is True
        hass.config_entries.async_unload_platforms.assert_called_once()

    async def test_unload_entry_not_setup(self, hass):
        """Test unloading an entry that was never setup."""
        from tests import create_mock_minimax_config_entry

        config_entry = create_mock_minimax_config_entry(hass)

        result = await async_unload_entry(hass, config_entry)

        assert result is True


class TestMiniMaxRuntimeData:
    """Test runtime_data access."""

    async def test_runtime_data_has_client(self, hass):
        """Test that runtime_data contains the API client."""
        from tests import create_mock_minimax_client, create_mock_minimax_config_entry

        config_entry = create_mock_minimax_config_entry(hass)
        mock_client = create_mock_minimax_client()

        with patch("custom_components.minimax.MiniMaxApiClient", return_value=mock_client):
            await async_setup_entry(hass, config_entry)

        assert config_entry.runtime_data is mock_client

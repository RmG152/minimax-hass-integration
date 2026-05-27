"""Tests for MiniMax integration init."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.minimax import async_setup_entry, async_unload_entry
from tests import (  # noqa: TID251
    create_mock_minimax_client,
    create_mock_minimax_config_entry,
)

pytest_plugins = "pytest_homeassistant_custom_component"


class TestAsyncSetupEntry:
    """Test async_setup_entry."""

    @pytest.mark.asyncio
    async def test_setup_entry_success(self, hass):
        """Test successful setup of entry."""
        config_entry = create_mock_minimax_config_entry(hass)
        mock_client = create_mock_minimax_client()

        with (
            patch(
                "custom_components.minimax.MiniMaxApiClient",
                return_value=mock_client,
            ),
            patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=True
            ),
        ):
            result = await async_setup_entry(hass, config_entry)

        assert result is True
        assert hasattr(config_entry, "runtime_data")
        assert config_entry.runtime_data is mock_client

    @pytest.mark.asyncio
    async def test_setup_entry_creates_client(self, hass):
        """Test that setup_entry creates an API client."""
        config_entry = create_mock_minimax_config_entry(hass)

        with (
            patch(
                "custom_components.minimax.MiniMaxApiClient",
            ) as mock_client_class,
            patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=True
            ),
        ):
            mock_instance = MagicMock()
            mock_instance.async_verify_connection = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_instance

            await async_setup_entry(hass, config_entry)

            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs["api_key"] == config_entry.data["api_key"]


class TestAsyncUnloadEntry:
    """Test async_unload_entry."""

    @pytest.mark.asyncio
    async def test_unload_entry_success(self, hass):
        """Test successful unload of entry."""
        config_entry = create_mock_minimax_config_entry(hass)
        mock_client = create_mock_minimax_client()

        with (
            patch(
                "custom_components.minimax.MiniMaxApiClient",
                return_value=mock_client,
            ),
            patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=True
            ),
        ):
            await async_setup_entry(hass, config_entry)

        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            result = await async_unload_entry(hass, config_entry)

        assert result is True

    @pytest.mark.asyncio
    async def test_unload_entry_not_setup(self, hass):
        """Test unloading an entry that was never setup."""
        config_entry = create_mock_minimax_config_entry(hass)

        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            result = await async_unload_entry(hass, config_entry)

        assert result is True


class TestMiniMaxApiClientRuntimeData:
    """Test runtime_data access."""

    @pytest.mark.asyncio
    async def test_runtime_data_has_client(self, hass):
        """Test that runtime_data contains the API client."""
        config_entry = create_mock_minimax_config_entry(hass)
        mock_client = create_mock_minimax_client()

        with (
            patch(
                "custom_components.minimax.MiniMaxApiClient",
                return_value=mock_client,
            ),
            patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=True
            ),
        ):
            await async_setup_entry(hass, config_entry)

        assert hasattr(config_entry, "runtime_data")
        assert config_entry.runtime_data is mock_client

    @pytest.mark.asyncio
    async def test_client_accessible_from_runtime_data(self, hass):
        """Test that client is accessible via runtime_data."""
        config_entry = create_mock_minimax_config_entry(hass)
        mock_client = create_mock_minimax_client()

        with (
            patch(
                "custom_components.minimax.MiniMaxApiClient",
                return_value=mock_client,
            ),
            patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=True
            ),
        ):
            await async_setup_entry(hass, config_entry)

        assert config_entry.runtime_data is mock_client

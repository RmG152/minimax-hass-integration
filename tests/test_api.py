"""Tests for MiniMax API client."""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import Response
import pytest
import respx

from custom_components.minimax.api import MiniMaxApiClient, MiniMaxApiClientError

TEST_API_KEY = "test_api_key_12345"


@pytest.fixture
async def api_client(aiohttp_client):
    """Create an API client for testing."""

    return MiniMaxApiClient(api_key=TEST_API_KEY, session=aiohttp_client)


class TestMiniMaxApiClientInit:
    """Test MiniMaxApiClient initialization."""

    def test_init(self, api_client: MiniMaxApiClient):
        """Test client initialization."""
        assert api_client._api_key == TEST_API_KEY  # noqa: SLF001


class TestAsyncChat:
    """Test async_chat method."""

    @pytest.mark.asyncio
    async def test_async_chat_success(self, api_client: MiniMaxApiClient):
        """Test successful chat request."""
        mock_response = {
            "id": "chatcmpl-123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello! How can I help you?"}],
            "model": "MiniMax-M2.7",
            "stop_reason": "end_turn",
        }

        with respx.mock(base_url="https://api.minimax.io") as respx_mock:
            respx_mock.post("/anthropic/v1/messages").mock(
                return_value=Response(200, json=mock_response)
            )
            result = await api_client.async_chat(
                model="MiniMax-M2.7",
                messages=[{"role": "user", "content": "Hi"}],
                system_prompt="You are helpful.",
            )

        assert result["success"] is True
        assert result["text"] == "Hello! How can I help you?"

    @pytest.mark.asyncio
    async def test_async_chat_with_tools(self, api_client: MiniMaxApiClient):
        """Test chat request with tools."""
        mock_response = {
            "id": "chatcmpl-123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Let me check the weather."}],
            "model": "MiniMax-M2.7",
            "stop_reason": "end_turn",
        }

        tools = [
            {
                "name": "get_weather",
                "description": "Get weather for a location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                    },
                },
            }
        ]

        with respx.mock(base_url="https://api.minimax.io") as respx_mock:
            respx_mock.post("/anthropic/v1/messages").mock(
                return_value=Response(200, json=mock_response)
            )
            result = await api_client.async_chat(
                model="MiniMax-M2.7",
                messages=[{"role": "user", "content": "What's the weather?"}],
                system_prompt="You are helpful.",
                tools=tools,
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_async_chat_http_error(self, api_client: MiniMaxApiClient):
        """Test chat request with HTTP error."""
        with respx.mock(base_url="https://api.minimax.io") as respx_mock:
            respx_mock.post("/anthropic/v1/messages").mock(
                return_value=Response(401, json={"error": "Unauthorized"})
            )
            result = await api_client.async_chat(
                model="MiniMax-M2.7",
                messages=[{"role": "user", "content": "Hi"}],
                system_prompt="You are helpful.",
            )

        assert result["success"] is False
        assert "401" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_async_chat_timeout(self, api_client: MiniMaxApiClient):
        """Test chat request with timeout."""
        with respx.mock(base_url="https://api.minimax.io") as respx_mock:
            respx_mock.post("/anthropic/v1/messages").mock(
                side_effect=Exception("Connection timed out")
            )
            result = await api_client.async_chat(
                model="MiniMax-M2.7",
                messages=[{"role": "user", "content": "Hi"}],
                system_prompt="You are helpful.",
            )

        assert result["success"] is False
        assert result.get("error") is not None


class TestAsyncTTS:
    """Test async_tts method."""

    @pytest.mark.asyncio
    async def test_async_tts_success(self, api_client: MiniMaxApiClient):
        """Test successful TTS request."""
        mock_audio_bytes = b"fake_audio_data"

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"data": {"audio": mock_audio_bytes.hex()}}
        )
        mock_response.raise_for_status = MagicMock()

        async def mock_post(*args, **kwargs):
            return mock_response

        class MockTimeout:
            def __init__(self, seconds):
                self._seconds = seconds

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __call__(self, coro):
                return coro

        def mock_timeout(seconds):
            return MockTimeout(seconds)

        mock_session = MagicMock()
        mock_session.post = mock_post

        with (
            patch(
                "custom_components.minimax.api.async_timeout.timeout",
                mock_timeout,
            ),
            patch.object(api_client, "_session", mock_session),
        ):
            result = await api_client.async_tts(
                text="Hello world",
                voice_id="English_PlayfulGirl",
                speed=1.0,
                vol=1.0,
                pitch=1.0,
                model="speech-2.8-hd",
            )

        assert result == mock_audio_bytes

    @pytest.mark.asyncio
    async def test_async_tts_http_error(self, api_client: MiniMaxApiClient):
        """Test TTS request with HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP 500"))
        mock_response.json = AsyncMock(return_value={})

        async def mock_post(*args, **kwargs):
            return mock_response

        class MockTimeout:
            def __init__(self, seconds):
                self._seconds = seconds

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __call__(self, coro):
                return coro

        def mock_timeout(seconds):
            return MockTimeout(seconds)

        mock_session = MagicMock()
        mock_session.post = mock_post

        with (
            patch(
                "custom_components.minimax.api.async_timeout.timeout",
                mock_timeout,
            ),
            patch.object(api_client, "_session", mock_session),
            pytest.raises(MiniMaxApiClientError),
        ):
            await api_client.async_tts(
                text="Hello world",
                voice_id="English_PlayfulGirl",
                speed=1.0,
                vol=1.0,
                pitch=1.0,
                model="speech-2.8-hd",
            )


class TestAsyncSTT:
    """Test async_stt method."""

    @pytest.mark.asyncio
    async def test_async_stt_success(self, api_client: MiniMaxApiClient):
        """Test successful STT request."""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"text": "This is transcribed text."}
        )
        mock_response.raise_for_status = MagicMock()

        async def mock_post(*args, **kwargs):
            return mock_response

        class MockTimeout:
            def __init__(self, seconds):
                self._seconds = seconds

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __call__(self, coro):
                return coro

        def mock_timeout(seconds):
            return MockTimeout(seconds)

        mock_session = MagicMock()
        mock_session.post = mock_post

        with (
            patch(
                "custom_components.minimax.api.async_timeout.timeout",
                mock_timeout,
            ),
            patch.object(api_client, "_session", mock_session),
        ):
            result = await api_client.async_stt(
                audio_data=b"fake_audio_content",
                model="MiniMax-M2.7",
                language="en-US",
                prompt="Transcribe the audio.",
                audio_format="wav",
            )

        assert result == "This is transcribed text."

    @pytest.mark.asyncio
    async def test_async_stt_http_error(self, api_client: MiniMaxApiClient):
        """Test STT request with HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP 500"))
        mock_response.json = AsyncMock(return_value={})

        async def mock_post(*args, **kwargs):
            return mock_response

        class MockTimeout:
            def __init__(self, seconds):
                self._seconds = seconds

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __call__(self, coro):
                return coro

        def mock_timeout(seconds):
            return MockTimeout(seconds)

        mock_session = MagicMock()
        mock_session.post = mock_post

        with (
            patch(
                "custom_components.minimax.api.async_timeout.timeout",
                mock_timeout,
            ),
            patch.object(api_client, "_session", mock_session),
            pytest.raises(MiniMaxApiClientError),
        ):
            await api_client.async_stt(
                audio_data=b"fake_audio_content",
                model="MiniMax-M2.7",
                language="en-US",
                prompt="Transcribe the audio.",
                audio_format="wav",
            )


class TestAsyncVerifyConnection:
    """Test async_verify_connection method."""

    @pytest.mark.asyncio
    async def test_verify_connection_success(self, api_client: MiniMaxApiClient):
        """Test successful connection verification."""
        mock_response = {
            "id": "verify-123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "ok"}],
            "model": "MiniMax-M2.7",
            "stop_reason": "end_turn",
        }

        with respx.mock(base_url="https://api.minimax.io") as respx_mock:
            respx_mock.post("/anthropic/v1/messages").mock(
                return_value=Response(200, json=mock_response)
            )
            result = await api_client.async_verify_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_connection_auth_failure(self, api_client: MiniMaxApiClient):
        """Test connection verification with auth failure."""
        with respx.mock(base_url="https://api.minimax.io") as respx_mock:
            respx_mock.post("/anthropic/v1/messages").mock(
                return_value=Response(401, json={"error": "Unauthorized"})
            )

            with pytest.raises(MiniMaxApiClientError) as exc_info:
                await api_client.async_verify_connection()

            assert "Invalid API key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_connection_rate_limit(self, api_client: MiniMaxApiClient):
        """Test connection verification with rate limit."""
        with respx.mock(base_url="https://api.minimax.io") as respx_mock:
            respx_mock.post("/anthropic/v1/messages").mock(
                return_value=Response(429, json={"error": "Rate limit exceeded"})
            )

            with pytest.raises(MiniMaxApiClientError) as exc_info:
                await api_client.async_verify_connection()

            assert "Connection failed" in str(exc_info.value)

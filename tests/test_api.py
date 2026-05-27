"""Tests for MiniMax API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.minimax.api import MiniMaxApiClient, MiniMaxApiClientError
from custom_components.minimax.const import (
    MINIMAX_ANTHROPIC_API_URL,
    MINIMAX_IMAGE_API,
    MINIMAX_STT_API,
    MINIMAX_TTS_API,
)

TEST_API_KEY = "test_api_key_12345"
TTS_AUDIO_HEX = "deadbeef"


@pytest.fixture
def mock_session():
    """Create a mock aiohttp ClientSession."""
    session = AsyncMock()
    session.post = AsyncMock()
    return session


@pytest.fixture
def mock_anthropic():
    """Create a mock anthropic AsyncAnthropic client."""
    with patch("custom_components.minimax.api.anthropic.AsyncAnthropic") as mock:
        instance = MagicMock()
        instance.messages = AsyncMock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def api_client(mock_session, mock_anthropic):
    """Create a MiniMaxApiClient for testing."""
    return MiniMaxApiClient(api_key=TEST_API_KEY, session=mock_session)


class TestMiniMaxApiClientInit:
    """Test MiniMaxApiClient initialization."""

    def test_init_stores_api_key(self, api_client):
        """Test client stores the API key."""
        assert api_client._api_key == TEST_API_KEY

    def test_init_creates_anthropic_client(self, mock_session):
        """Test client creates an Anthropic client."""
        with patch(
            "custom_components.minimax.api.anthropic.AsyncAnthropic"
        ) as mock_anth:
            MiniMaxApiClient(api_key=TEST_API_KEY, session=mock_session)
            mock_anth.assert_called_once()
            call_kwargs = mock_anth.call_args[1]
            assert call_kwargs["api_key"] == TEST_API_KEY
            assert MINIMAX_ANTHROPIC_API_URL.rsplit("/v1", 1)[0] in str(
                call_kwargs["base_url"]
            )

    def test_init_stores_session(self, api_client, mock_session):
        """Test client stores the aiohttp session."""
        assert api_client._session is mock_session


def _make_text_block(text: str) -> MagicMock:
    """Create a mock content block with type text."""
    block = MagicMock(spec=["type", "text"])
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(id_: str, name: str, input_: dict) -> MagicMock:
    """Create a mock content block with type tool_use."""
    block = MagicMock(spec=["type", "id", "name", "input"])
    block.type = "tool_use"
    block.id = id_
    block.name = name
    block.input = input_
    return block


def _make_thinking_block() -> MagicMock:
    """Create a mock content block with type thinking."""
    block = MagicMock(spec=["type"])
    block.type = "thinking"
    return block


def _make_chat_response(content: list, stop_reason: str = "end_turn") -> MagicMock:
    """Create a mock chat response."""
    resp = MagicMock()
    resp.content = content
    resp.stop_reason = stop_reason
    return resp


class TestAsyncChat:
    """Test async_chat method."""

    async def test_success(self, api_client, mock_anthropic):
        """Test successful chat request."""
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_chat_response(
                [_make_text_block("Hello! How can I help you?")]
            )
        )

        result = await api_client.async_chat(
            model="MiniMax-M2.7",
            messages=[{"role": "user", "content": "Hi"}],
            system_prompt="You are helpful.",
        )

        assert result["success"] is True
        assert result["text"] == "Hello! How can I help you?"
        assert result["tool_calls"] == []
        assert result["stop_reason"] == "end_turn"
        assert result["content"] == [
            {"type": "text", "text": "Hello! How can I help you?"}
        ]

    async def test_with_tools(self, api_client, mock_anthropic):
        """Test chat request passes tools to API."""
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_chat_response([_make_text_block("Let me check.")])
        )

        tools = [
            {"name": "get_weather", "description": "Get weather", "input_schema": {}}
        ]
        await api_client.async_chat(
            model="MiniMax-M2.7",
            messages=[],
            system_prompt="",
            tools=tools,
        )

        call_kwargs = mock_anthropic.messages.create.call_args[1]
        assert call_kwargs["tools"] == tools

    async def test_with_tool_calls_in_response(self, api_client, mock_anthropic):
        """Test chat response with tool calls."""
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_chat_response(
                [
                    _make_text_block("Turning on light."),
                    _make_tool_use_block(
                        "toolu_1", "light.turn_on", {"entity_id": "light.living_room"}
                    ),
                ],
                stop_reason="tool_use",
            )
        )

        result = await api_client.async_chat(
            model="MiniMax-M2.7", messages=[], system_prompt=""
        )

        assert result["success"] is True
        assert result["text"] == "Turning on light."
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "toolu_1"
        assert result["tool_calls"][0]["name"] == "light.turn_on"
        assert len(result["content"]) == 2
        assert result["content"][0] == {"type": "text", "text": "Turning on light."}
        assert result["content"][1] == {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "light.turn_on",
            "input": {"entity_id": "light.living_room"},
        }

    async def test_with_thinking_blocks_ignored(self, api_client, mock_anthropic):
        """Test thinking blocks are ignored in response."""
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_chat_response(
                [_make_thinking_block(), _make_text_block("Final answer")]
            )
        )

        result = await api_client.async_chat(
            model="MiniMax-M2.7", messages=[], system_prompt=""
        )

        assert result["success"] is True
        assert result["text"] == "Final answer"
        assert result["content"] == [{"type": "text", "text": "Final answer"}]

    async def test_api_error_returns_error_dict(self, api_client, mock_anthropic):
        """Test API error returns error dict instead of raising."""
        mock_anthropic.messages.create = AsyncMock(
            side_effect=Exception("API rate limit exceeded")
        )

        result = await api_client.async_chat(
            model="MiniMax-M2.7", messages=[], system_prompt=""
        )

        assert result["success"] is False
        assert "error" in result

    async def test_empty_content(self, api_client, mock_anthropic):
        """Test empty content returns empty text."""
        mock_anthropic.messages.create = AsyncMock(return_value=_make_chat_response([]))

        result = await api_client.async_chat(
            model="MiniMax-M2.7", messages=[], system_prompt=""
        )

        assert result["success"] is True
        assert result["text"] == ""
        assert result["content"] == []


class TestAsyncTTS:
    """Test async_tts method."""

    async def test_success(self, api_client, mock_session):
        """Test successful TTS request."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "data": {"audio": TTS_AUDIO_HEX},
            }
        )
        mock_session.post.return_value = mock_response

        result = await api_client.async_tts(
            text="Hello world",
            voice_id="English_PlayfulGirl",
            speed=1.0,
            vol=1.0,
            pitch=0,
            model="speech-2.8-hd",
        )

        assert result == bytes.fromhex(TTS_AUDIO_HEX)
        mock_session.post.assert_called_once_with(
            MINIMAX_TTS_API,
            headers={
                "Authorization": f"Bearer {TEST_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "speech-2.8-hd",
                "text": "Hello world",
                "stream": False,
                "voice_setting": {
                    "voice_id": "English_PlayfulGirl",
                    "speed": 1.0,
                    "vol": 1.0,
                    "pitch": 0,
                },
            },
        )

    async def test_http_error(self, api_client, mock_session):
        """Test TTS request with HTTP error."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP 500"))
        mock_session.post.return_value = mock_response

        with pytest.raises(MiniMaxApiClientError):
            await api_client.async_tts(
                text="Hello",
                voice_id="English_PlayfulGirl",
                speed=1.0,
                vol=1.0,
                pitch=0,
                model="speech-2.8-hd",
            )

    async def test_empty_audio_data(self, api_client, mock_session):
        """Test TTS request with no audio data in response."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"data": {}})
        mock_session.post.return_value = mock_response

        with pytest.raises(MiniMaxApiClientError):
            await api_client.async_tts(
                text="Hello",
                voice_id="English_PlayfulGirl",
                speed=1.0,
                vol=1.0,
                pitch=0,
                model="speech-2.8-hd",
            )


class TestAsyncSTT:
    """Test async_stt method."""

    async def test_success(self, api_client, mock_session):
        """Test successful STT request."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "text": "Transcribed text.",
                "code": 0,
                "msg": "success",
            }
        )
        mock_session.post.return_value = mock_response

        result = await api_client.async_stt(
            audio_data=b"fake",
            model="MiniMax-M2.7",
            language="en-US",
            prompt="Transcribe",
            audio_format="wav",
        )

        assert result == "Transcribed text."
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == MINIMAX_STT_API
        assert "Authorization" in call_args[1]["headers"]

    async def test_http_error(self, api_client, mock_session):
        """Test STT request with HTTP error."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP 500"))
        mock_session.post.return_value = mock_response

        with pytest.raises(MiniMaxApiClientError):
            await api_client.async_stt(
                audio_data=b"test",
                model="MiniMax-M2.7",
                language="en-US",
                prompt="",
                audio_format="wav",
            )

    async def test_empty_text_response(self, api_client, mock_session):
        """Test STT with empty text response."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"text": "", "code": 0})
        mock_session.post.return_value = mock_response

        with pytest.raises(MiniMaxApiClientError):
            await api_client.async_stt(
                audio_data=b"test",
                model="MiniMax-M2.7",
                language="en-US",
                prompt="",
                audio_format="wav",
            )


class TestAsyncImageGeneration:
    """Test async_image_generation method."""

    async def test_success_base64(self, api_client, mock_session):
        """Test image generation with base64 response."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "data": {"image_base64": ["ZmFrZV9pbWFnZQ=="]},
            }
        )
        mock_session.post.return_value = mock_response

        result = await api_client.async_image_generation(
            prompt="A cat", model="image-01"
        )

        assert result == b"fake_image"
        mock_session.post.assert_called_once_with(
            MINIMAX_IMAGE_API,
            headers={
                "Authorization": f"Bearer {TEST_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "image-01",
                "prompt": "A cat",
                "aspect_ratio": "1:1",
                "response_format": "base64",
            },
        )

    async def test_success_url(self, api_client, mock_session):
        """Test image generation with URL response."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "data": {"image_urls": ["https://api.minimax.io/img.jpg"]},
            }
        )
        mock_session.post.return_value = mock_response

        with patch("custom_components.minimax.api.httpx.AsyncClient") as mock_httpx:
            mock_ctx = MagicMock()
            mock_httpx.return_value = mock_ctx
            mock_client = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.content = b"image_from_url"
            mock_client.get.return_value = mock_resp

            result = await api_client.async_image_generation(
                prompt="A cat",
                model="image-01",
                response_format="url",
            )

        assert result == b"image_from_url"

    async def test_http_error(self, api_client, mock_session):
        """Test image generation with HTTP error."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP 500"))
        mock_session.post.return_value = mock_response

        with pytest.raises(MiniMaxApiClientError):
            await api_client.async_image_generation(prompt="A cat", model="image-01")

    async def test_empty_response(self, api_client, mock_session):
        """Test image generation with empty data."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"data": {}})
        mock_session.post.return_value = mock_response

        with pytest.raises(MiniMaxApiClientError):
            await api_client.async_image_generation(prompt="A cat", model="image-01")


class TestAsyncVerifyConnection:
    """Test async_verify_connection method."""

    async def test_success(self, api_client, mock_anthropic):
        """Test successful connection verification."""
        mock_anthropic.messages.create = AsyncMock(
            return_value=_make_chat_response([_make_text_block("ok")])
        )

        result = await api_client.async_verify_connection()

        assert result is True

    async def test_auth_failure(self, api_client):
        """Test verification with auth failure."""
        api_client.async_chat = AsyncMock(
            return_value={"success": False, "error": "401 Unauthorized"}
        )

        with pytest.raises(MiniMaxApiClientError, match="Invalid API key"):
            await api_client.async_verify_connection()

    async def test_connection_error(self, api_client):
        """Test verification with connection error."""
        api_client.async_chat = AsyncMock(
            return_value={"success": False, "error": "Connection refused"}
        )

        with pytest.raises(MiniMaxApiClientError, match="Connection failed"):
            await api_client.async_verify_connection()

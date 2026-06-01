"""Tests for MiniMax WebSocket client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.minimax.websocket_client import MiniMaxWebSocketClient

TEST_API_KEY = "test_ws_api_key"


def _make_text_msg(event):
    """Create a mock TEXT WS message."""
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.data = json.dumps(event)
    return msg


def _make_error_msg():
    """Create a mock ERROR WS message."""
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.ERROR
    return msg


class TestWebSocketClientInit:
    """Test MiniMaxWebSocketClient initialization."""

    def test_init_stores_fields(self):
        """Test that all init parameters are stored."""
        hass = MagicMock()
        client = MiniMaxWebSocketClient(
            hass=hass,
            api_key=TEST_API_KEY,
            model="speech-2.8-hd",
            voice="English_PlayfulGirl",
            language="en-US",
            speed=1.0,
            vol=0.8,
            pitch=2,
        )
        assert client._hass is hass
        assert client._api_key == TEST_API_KEY
        assert client._voice == "English_PlayfulGirl"
        assert client._model == "speech-2.8-hd"
        assert client._language == "en-US"
        assert client._speed == 1.0
        assert client._vol == 0.8
        assert client._pitch == 2
        assert client._file_format == "mp3"
        assert client._url == "wss://api.minimax.io/ws/v1/t2a_v2"


def _build_async_iter(messages):
    """Build an async iterator yielding the given messages."""

    async def _aiter():
        for m in messages:
            yield m

    return _aiter()


class TestWebSocketSynthesize:
    """Test MiniMaxWebSocketClient.synthesize."""

    @pytest.fixture
    def client(self, hass):
        """Create a websocket client."""
        return MiniMaxWebSocketClient(
            hass=hass,
            api_key=TEST_API_KEY,
            model="speech-2.8-hd",
            voice="English_PlayfulGirl",
            language="en-US",
            speed=1.0,
            vol=1.0,
            pitch=0,
        )

    @pytest.mark.asyncio
    async def test_synthesize_success(self, client):
        """Test successful audio synthesis returns bytes."""
        start_msgs = [_make_text_msg({"event": "task_started"})]
        audio_msgs = [
            _make_text_msg({"event": "task_continued", "data": {"audio": "deadbeef"}}),
            _make_text_msg({"event": "task_finished", "is_final": True}),
        ]

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            start_msgs + audio_msgs
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hello world")

        assert result == bytes.fromhex("deadbeef")

    @pytest.mark.asyncio
    async def test_synthesize_task_error_during_start(self, client):
        """Test task_error event during handshake returns None."""
        error_msg = _make_text_msg(
            {"event": "task_error", "msg": "Something went wrong"}
        )
        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter([error_msg]).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hello")

        assert result is None

    @pytest.mark.asyncio
    async def test_synthesize_websocket_error_during_start(self, client):
        """Test WebSocket ERROR message during handshake returns None."""
        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter([_make_error_msg()]).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hello")

        assert result is None

    @pytest.mark.asyncio
    async def test_synthesize_never_started_returns_none(self, client):
        """Test handshake that never receives task_started returns None."""
        unknown_msg = _make_text_msg({"event": "something_else"})

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter([unknown_msg]).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hi")

        assert result is None

    @pytest.mark.asyncio
    async def test_synthesize_invalid_json_during_start_skipped(self, client):
        """Test invalid JSON during handshake is skipped until task_started."""
        invalid_msg = _make_text_msg_raw("not json")
        start_msg = _make_text_msg({"event": "task_started"})
        audio_msg = _make_text_msg(
            {"event": "task_finished", "is_final": True, "data": {"audio": "abcd"}}
        )

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            [invalid_msg, start_msg, audio_msg]
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hi")

        assert result == bytes.fromhex("abcd")

    @pytest.mark.asyncio
    async def test_synthesize_task_error_during_audio(self, client):
        """Test task_error during audio streaming breaks the loop."""
        start_msg = _make_text_msg({"event": "task_started"})
        error_msg = _make_text_msg({"event": "task_error"})

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            [start_msg, error_msg]
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hi")

        assert result is None

    @pytest.mark.asyncio
    async def test_synthesize_websocket_error_during_audio(self, client):
        """Test WebSocket ERROR message during audio streaming breaks loop."""
        start_msg = _make_text_msg({"event": "task_started"})
        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            [start_msg, _make_error_msg()]
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hi")

        assert result is None

    @pytest.mark.asyncio
    async def test_synthesize_no_audio_returns_none(self, client):
        """Test synthesis with no audio data returns None."""
        start_msg = _make_text_msg({"event": "task_started"})
        finished_msg = _make_text_msg({"event": "task_finished", "is_final": True})

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            [start_msg, finished_msg]
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hi")

        assert result is None

    @pytest.mark.asyncio
    async def test_synthesize_exception_returns_none(self, client):
        """Test that an exception during connection returns None."""
        session = MagicMock()
        session.ws_connect = MagicMock(side_effect=Exception("connection boom"))

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hi")

        assert result is None

    @pytest.mark.asyncio
    async def test_synthesize_sends_start_payload(self, client):
        """Test start payload includes voice settings and audio settings."""
        start_msg = _make_text_msg({"event": "task_started"})
        finished_msg = _make_text_msg({"event": "task_finished", "is_final": True})

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            [start_msg, finished_msg]
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            await client.synthesize("Hi")

        first_payload = ws.send_json.call_args_list[0][0][0]
        assert first_payload["event"] == "task_start"
        assert first_payload["model"] == "speech-2.8-hd"
        assert first_payload["voice_setting"]["voice_id"] == "English_PlayfulGirl"
        assert first_payload["voice_setting"]["pitch"] == 0
        assert first_payload["audio_setting"]["format"] == "mp3"

    @pytest.mark.asyncio
    async def test_synthesize_sends_continue_and_finish(self, client):
        """Test continue and finish payloads are sent after task_started."""
        start_msg = _make_text_msg({"event": "task_started"})
        finished_msg = _make_text_msg({"event": "task_finished", "is_final": True})

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            [start_msg, finished_msg]
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            await client.synthesize("Hello there")

        sent = [c.args[0] for c in ws.send_json.call_args_list]
        events = [s["event"] for s in sent]
        assert events == ["task_start", "task_continue", "task_finish"]
        assert sent[1]["text"] == "Hello there"

    @pytest.mark.asyncio
    async def test_synthesize_sends_authorization_header(self, client):
        """Test authorization header is passed to ws_connect."""
        start_msg = _make_text_msg({"event": "task_started"})
        finished_msg = _make_text_msg({"event": "task_finished", "is_final": True})

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            [start_msg, finished_msg]
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            await client.synthesize("Hi")

        headers = session.ws_connect.call_args[1]["headers"]
        assert headers["Authorization"] == f"Bearer {TEST_API_KEY}"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_synthesize_invalid_json_during_audio_skipped(self, client):
        """Test invalid JSON during audio streaming is skipped."""
        start_msg = _make_text_msg({"event": "task_started"})
        invalid_msg = _make_text_msg_raw("{not json")
        audio_msg = _make_text_msg(
            {"event": "task_finished", "is_final": True, "data": {"audio": "ff"}}
        )

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            [start_msg, invalid_msg, audio_msg]
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hi")

        assert result == bytes.fromhex("ff")

    @pytest.mark.asyncio
    async def test_synthesize_concatenates_multiple_chunks(self, client):
        """Test multiple audio chunks are concatenated in order."""
        start_msg = _make_text_msg({"event": "task_started"})
        chunk1 = _make_text_msg({"event": "task_continued", "data": {"audio": "aa"}})
        chunk2 = _make_text_msg({"event": "task_continued", "data": {"audio": "bb"}})
        finished = _make_text_msg({"event": "task_finished", "is_final": True})

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            [start_msg, chunk1, chunk2, finished]
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            result = await client.synthesize("Hi")

        assert result == bytes.fromhex("aabb")

    @pytest.mark.asyncio
    async def test_synthesize_pitch_coerced_to_int(self, client):
        """Test pitch is coerced to int in start payload."""
        client._pitch = 2.7
        start_msg = _make_text_msg({"event": "task_started"})
        finished_msg = _make_text_msg({"event": "task_finished", "is_final": True})

        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.__aiter__ = lambda self: _build_async_iter(
            [start_msg, finished_msg]
        ).__aiter__()

        session = MagicMock()
        ws_cm = MagicMock()
        ws_cm.__aenter__ = AsyncMock(return_value=ws)
        ws_cm.__aexit__ = AsyncMock(return_value=False)
        session.ws_connect = MagicMock(return_value=ws_cm)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=session,
        ):
            await client.synthesize("Hi")

        first_payload = ws.send_json.call_args_list[0][0][0]
        assert first_payload["voice_setting"]["pitch"] == 2


def _make_text_msg_raw(raw_text):
    """Create a mock TEXT WS message with raw (possibly non-JSON) data."""
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.data = raw_text
    return msg

"""Tests for the streaming MiniMax T2A v2 WebSocket client."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.minimax.const import DEFAULT_PITCH, DEFAULT_SPEED, DEFAULT_VOL
from custom_components.minimax.websocket_client import MiniMaxT2AWebSocketClient
from homeassistant.exceptions import HomeAssistantError

TEST_API_KEY = "test_ws_api_key"
TEST_MODEL = "speech-2.8-hd"
TEST_VOICE = "English_PlayfulGirl"


def _make_text_msg(event: dict[str, Any]) -> MagicMock:
    """Create a mock TEXT WS message carrying a JSON event."""
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.data = json.dumps(event)
    return msg


def _make_closing_msg() -> MagicMock:
    """Create a mock CLOSING WS message."""
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.CLOSING
    return msg


def _build_websocket_mock(
    receive_events: list[dict[str, Any]] | None = None,
    iter_events: list[dict[str, Any]] | None = None,
    raise_on_connect: Exception | None = None,
) -> MagicMock:
    """Build a mock ClientWebSocketResponse.

    Real aiohttp exposes ``ws.receive()`` and ``async for msg in ws``; both
    consume the same underlying message stream. This mock mirrors that by
    pulling from one shared queue: ``receive()`` first, then ``__aiter__``
    after.

    - ``receive_events`` are the messages returned by the first ``receive()``
      calls.
    - ``iter_events`` are the messages returned by subsequent ``__aiter__``
      iterations.
    - If ``raise_on_connect`` is set, ``ws_connect`` raises it.
    """
    ws = MagicMock()
    ws.closed = False
    ws.close = AsyncMock()

    if receive_events is None:
        receive_events = [
            {"event": "connected_success"},
            {"event": "task_started"},
        ]
    if iter_events is None:
        iter_events = []

    queue: list[Any] = [_make_text_msg(e) for e in (receive_events + iter_events)]

    async def _receive() -> Any:
        if not queue:
            return _make_closing_msg()
        return queue.pop(0)

    ws.receive = AsyncMock(side_effect=_receive)
    ws.__aiter__ = MagicMock(return_value=_ReceiveIterator(_receive))

    sent: list[dict[str, Any]] = []
    ws.sent = sent

    async def _send_json(payload: dict[str, Any]) -> None:
        sent.append(payload)

    ws.send_json = AsyncMock(side_effect=_send_json)
    return ws


class _ReceiveIterator:
    """Async iterator that pulls messages via the same receive() coroutine."""

    def __init__(self, receive_coro) -> None:
        """Store the receive coroutine to call on each iteration."""
        self._receive = receive_coro

    def __aiter__(self) -> "_ReceiveIterator":
        """Return self as the async iterator."""
        return self

    async def __anext__(self) -> Any:
        """Return the next message or stop iteration on close/empty."""
        msg = await self._receive()
        if msg.type in (
            aiohttp.WSMsgType.CLOSE,
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.CLOSING,
        ):
            raise StopAsyncIteration
        return msg


async def _empty_text_chunks() -> Any:
    """Async generator that yields nothing and exits."""
    if False:
        yield ""


def _make_client(hass: MagicMock, **overrides: Any) -> MiniMaxT2AWebSocketClient:
    """Build a client with sensible defaults."""
    kwargs: dict[str, Any] = {
        "hass": hass,
        "api_key": TEST_API_KEY,
        "model": TEST_MODEL,
        "voice_id": TEST_VOICE,
        "language_boost": None,
        "speed": DEFAULT_SPEED,
        "vol": DEFAULT_VOL,
        "pitch": DEFAULT_PITCH,
        "audio_format": "mp3",
        "sample_rate": 32000,
    }
    kwargs.update(overrides)
    return MiniMaxT2AWebSocketClient(**kwargs)


class TestClientInit:
    """Test constructor parameter storage."""

    def test_init_stores_fields(self):
        """All init parameters are stored as instance attributes."""
        hass = MagicMock()
        client = _make_client(
            hass,
            voice_id="English_Comedian",
            language_boost="Chinese",
            speed=1.5,
            vol=0.7,
            pitch=-3,
            audio_format="opus",
            sample_rate=44100,
        )
        assert client._hass is hass
        assert client._api_key == TEST_API_KEY
        assert client._model == TEST_MODEL
        assert client._voice_id == "English_Comedian"
        assert client._language_boost == "Chinese"
        assert client._speed == 1.5
        assert client._vol == 0.7
        assert client._pitch == -3
        assert client._audio_format == "opus"
        assert client._sample_rate == 44100


class TestBuildStartPayload:
    """Test the task_start event payload."""

    def test_payload_contains_required_fields(self):
        """The task_start payload has model, voice_setting, audio_setting."""
        client = _make_client(MagicMock())
        payload = client._build_start_payload()
        assert payload["event"] == "task_start"
        assert payload["model"] == TEST_MODEL
        assert payload["voice_setting"]["voice_id"] == TEST_VOICE
        assert payload["voice_setting"]["speed"] == DEFAULT_SPEED
        assert payload["voice_setting"]["vol"] == DEFAULT_VOL
        assert payload["voice_setting"]["pitch"] == DEFAULT_PITCH
        assert payload["audio_setting"]["format"] == "mp3"
        assert payload["audio_setting"]["sample_rate"] == 32000
        assert payload["audio_setting"]["channel"] == 1

    def test_payload_omits_language_boost_when_none(self):
        """language_boost is not present when set to None."""
        client = _make_client(MagicMock(), language_boost=None)
        payload = client._build_start_payload()
        assert "language_boost" not in payload

    def test_payload_includes_language_boost_when_set(self):
        """language_boost is included when non-empty."""
        client = _make_client(MagicMock(), language_boost="English")
        payload = client._build_start_payload()
        assert payload["language_boost"] == "English"

    def test_payload_omits_language_boost_when_empty(self):
        """language_boost is omitted on empty string (falsy)."""
        client = _make_client(MagicMock(), language_boost="")
        payload = client._build_start_payload()
        assert "language_boost" not in payload


class TestStreamLifecycle:
    """End-to-end behaviour of stream()."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Patch aiohttp_client.async_get_clientsession with a mock session."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_stream_sends_task_start_with_correct_settings(self, mock_session):
        """task_start payload is sent first, with model and voice settings."""
        ws = _build_websocket_mock()
        mock_session.ws_connect = AsyncMock(return_value=ws)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(
                MagicMock(),
                voice_id="English_Comedian",
                speed=1.2,
                vol=0.9,
                pitch=2,
            )
            async for _chunk in client.stream(_empty_text_chunks()):
                pass

        sent_events = [m["event"] for m in ws.sent]
        assert sent_events[0] == "task_start"
        assert sent_events[-1] == "task_finish"
        first = ws.sent[0]
        assert first["model"] == TEST_MODEL
        assert first["voice_setting"]["voice_id"] == "English_Comedian"
        assert first["voice_setting"]["speed"] == 1.2
        assert first["voice_setting"]["vol"] == 0.9
        assert first["voice_setting"]["pitch"] == 2

    @pytest.mark.asyncio
    async def test_stream_sends_one_task_continue_per_sentence(self, mock_session):
        """Each text chunk is sent as a task_continue event."""
        ws = _build_websocket_mock()
        mock_session.ws_connect = AsyncMock(return_value=ws)

        async def two_sentences() -> Any:
            yield "First sentence. "
            yield "Second sentence."

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(MagicMock())
            async for _ in client.stream(two_sentences()):
                pass

        sent_events = [m["event"] for m in ws.sent]
        assert sent_events == [
            "task_start",
            "task_continue",
            "task_continue",
            "task_finish",
        ]
        continue_payloads = [m for m in ws.sent if m["event"] == "task_continue"]
        assert continue_payloads[0]["text"] == "First sentence. "
        assert continue_payloads[1]["text"] == "Second sentence."

    @pytest.mark.asyncio
    async def test_stream_yields_audio_chunks_in_order(self, mock_session):
        """Audio hex payloads are decoded and yielded in arrival order."""
        audio1 = "deadbeef"
        audio2 = "cafebabe"
        iter_events = [
            {"data": {"audio": audio1}},
            {"data": {"audio": audio2}},
            {"is_final": True},
        ]
        ws = _build_websocket_mock(iter_events=iter_events)
        mock_session.ws_connect = AsyncMock(return_value=ws)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(MagicMock())
            collected = [chunk async for chunk in client.stream(_empty_text_chunks())]

        assert collected == [bytes.fromhex(audio1), bytes.fromhex(audio2)]

    @pytest.mark.asyncio
    async def test_stream_sends_task_finish_on_normal_completion(self, mock_session):
        """task_finish is sent once the input iterator is exhausted."""
        ws = _build_websocket_mock()
        mock_session.ws_connect = AsyncMock(return_value=ws)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(MagicMock())
            async for _ in client.stream(_empty_text_chunks()):
                pass

        assert ws.sent[-1]["event"] == "task_finish"

    @pytest.mark.asyncio
    async def test_stream_closes_websocket_on_completion(self, mock_session):
        """The WS is closed when the stream ends normally."""
        ws = _build_websocket_mock()
        mock_session.ws_connect = AsyncMock(return_value=ws)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(MagicMock())
            async for _ in client.stream(_empty_text_chunks()):
                pass

        ws.close.assert_awaited()

    @pytest.mark.asyncio
    async def test_stream_skips_empty_text_chunks(self, mock_session):
        """Empty string chunks are not forwarded to the server."""
        ws = _build_websocket_mock()
        mock_session.ws_connect = AsyncMock(return_value=ws)

        async def mixed_chunks() -> Any:
            yield ""
            yield "Real text."
            yield ""

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(MagicMock())
            async for _ in client.stream(mixed_chunks()):
                pass

        continue_payloads = [m for m in ws.sent if m["event"] == "task_continue"]
        assert len(continue_payloads) == 1
        assert continue_payloads[0]["text"] == "Real text."

    @pytest.mark.asyncio
    async def test_stream_raises_home_assistant_error_on_task_error(self, mock_session):
        """A task_error event during connect raises HomeAssistantError."""
        ws = _build_websocket_mock(
            receive_events=[
                {"event": "task_error", "base_resp": {"status_msg": "nope"}}
            ]
        )
        mock_session.ws_connect = AsyncMock(return_value=ws)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(MagicMock())
            with pytest.raises(HomeAssistantError, match="during connect"):
                async for _ in client.stream(_empty_text_chunks()):
                    pass

    @pytest.mark.asyncio
    async def test_stream_raises_on_unexpected_connect_event(self, mock_session):
        """A non-connected_success first message is rejected."""
        ws = _build_websocket_mock(receive_events=[{"event": "something_else"}])
        mock_session.ws_connect = AsyncMock(return_value=ws)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(MagicMock())
            with pytest.raises(HomeAssistantError, match="expected connected_success"):
                async for _ in client.stream(_empty_text_chunks()):
                    pass

    @pytest.mark.asyncio
    async def test_stream_wraps_connection_errors(self, mock_session):
        """A aiohttp ClientError is wrapped as HomeAssistantError."""
        mock_session.ws_connect = AsyncMock(side_effect=aiohttp.ClientError("boom"))

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(MagicMock())
            with pytest.raises(HomeAssistantError, match="WebSocket error"):
                async for _ in client.stream(_empty_text_chunks()):
                    pass

    @pytest.mark.asyncio
    async def test_stream_raises_on_invalid_json_during_handshake(self, mock_session):
        """Non-JSON first message raises HomeAssistantError."""
        ws = MagicMock()
        ws.closed = False
        ws.close = AsyncMock()
        ws.sent = []
        ws.send_json = AsyncMock(side_effect=lambda p: ws.sent.append(p))
        bad_msg = MagicMock()
        bad_msg.type = aiohttp.WSMsgType.TEXT
        bad_msg.data = "{not json"
        ws.receive = AsyncMock(return_value=bad_msg)
        ws.__aiter__ = MagicMock(return_value=_ReceiveIterator(ws.receive))
        mock_session.ws_connect = AsyncMock(return_value=ws)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(MagicMock())
            with pytest.raises(HomeAssistantError, match="invalid JSON"):
                async for _ in client.stream(_empty_text_chunks()):
                    pass

    @pytest.mark.asyncio
    async def test_stream_raises_on_close_during_handshake(self, mock_session):
        """A CLOSE message during handshake is rejected."""
        ws = MagicMock()
        ws.closed = False
        ws.close = AsyncMock()
        ws.sent = []
        ws.send_json = AsyncMock(side_effect=lambda p: ws.sent.append(p))
        ws.receive = AsyncMock(return_value=_make_closing_msg())
        ws.__aiter__ = MagicMock(return_value=_ReceiveIterator(ws.receive))
        mock_session.ws_connect = AsyncMock(return_value=ws)

        with patch(
            "custom_components.minimax.websocket_client.async_get_clientsession",
            return_value=mock_session,
        ):
            client = _make_client(MagicMock())
            with pytest.raises(HomeAssistantError, match="closed unexpectedly"):
                async for _ in client.stream(_empty_text_chunks()):
                    pass

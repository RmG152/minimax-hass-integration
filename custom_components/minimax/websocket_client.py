"""Streaming TTS client for the MiniMax T2A v2 WebSocket API."""

import asyncio
from collections.abc import AsyncIterator
import contextlib
import json
import logging

from aiohttp import ClientError, ClientWebSocketResponse, WSMsgType

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class MiniMaxT2AWebSocketClient:
    """Streaming TTS client for the MiniMax T2A v2 WebSocket API.

    One instance, one connection. Call stream() once and let it close.
    """

    _URL = "wss://api.minimax.io/ws/v1/t2a_v2"

    _EVENT_CONNECTED_SUCCESS = "connected_success"
    _EVENT_TASK_STARTED = "task_started"
    _EVENT_TASK_FINISHED = "task_finished"
    _EVENT_TASK_ERROR = "task_error"

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        model: str,
        voice_id: str,
        language_boost: str | None,
        speed: float,
        vol: float,
        pitch: int,
        audio_format: str = "mp3",
        sample_rate: int = 32000,
    ) -> None:
        """Initialize the WebSocket TTS client."""
        self._hass = hass
        self._api_key = api_key
        self._model = model
        self._voice_id = voice_id
        self._language_boost = language_boost
        self._speed = speed
        self._vol = vol
        self._pitch = pitch
        self._audio_format = audio_format
        self._sample_rate = sample_rate

    async def stream(self, text_chunks: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """Connect, configure, accept sentences, yield audio bytes, close.

        Cancellation-safe: always sends task_finish and closes the socket.
        """
        _LOGGER.debug(
            "MiniMax TTS WS open: model=%s voice=%s format=%s sample_rate=%d "
            "speed=%.2f vol=%.2f pitch=%d language_boost=%s",
            self._model,
            self._voice_id,
            self._audio_format,
            self._sample_rate,
            self._speed,
            self._vol,
            self._pitch,
            self._language_boost,
        )
        session = async_get_clientsession(self._hass)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        read_task: asyncio.Task[None] | None = None
        ws: ClientWebSocketResponse | None = None

        try:
            ws = await session.ws_connect(self._URL, headers=headers)

            await self._expect_event(ws, self._EVENT_CONNECTED_SUCCESS, "connect")

            start_payload = self._build_start_payload()
            _LOGGER.debug("MiniMax TTS WS -> task_start: %s", start_payload)
            await ws.send_json(start_payload)
            await self._expect_event(ws, self._EVENT_TASK_STARTED, "task_start")

            read_task = asyncio.create_task(
                self._read_loop(ws, queue), name="minimax_t2a_ws_read"
            )

            buffered: list[str] = [chunk async for chunk in text_chunks if chunk]
            full_text = "".join(buffered)

            if full_text:
                _LOGGER.debug(
                    "MiniMax TTS WS -> task_continue: %d char(s) buffered",
                    len(full_text),
                )
                await ws.send_json({"event": "task_continue", "text": full_text})

            _LOGGER.debug(
                "MiniMax TTS WS: text exhausted (%d char(s)), sending task_finish",
                len(full_text),
            )
            with contextlib.suppress(ConnectionResetError, ClientError, RuntimeError):
                await ws.send_json({"event": "task_finish"})

            total_bytes = 0
            chunk_count = 0
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                chunk_count += 1
                total_bytes += len(chunk)
                yield chunk

            _LOGGER.debug(
                "MiniMax TTS WS done: %d audio chunk(s), %d byte(s) total (format=%s)",
                chunk_count,
                total_bytes,
                self._audio_format,
            )

        except ClientError as err:
            raise HomeAssistantError(f"MiniMax TTS WebSocket error: {err}") from err
        finally:
            if read_task is not None and not read_task.done():
                read_task.cancel()
            if read_task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await read_task
            if ws is not None and not ws.closed:
                _LOGGER.debug("MiniMax TTS WS close")
                with contextlib.suppress(Exception):
                    await ws.close()

    def _build_start_payload(self) -> dict:
        """Build the task_start event payload."""
        payload: dict = {
            "event": "task_start",
            "model": self._model,
            "voice_setting": {
                "voice_id": self._voice_id,
                "speed": self._speed,
                "vol": self._vol,
                "pitch": int(self._pitch),
                "english_normalization": False,
            },
            "audio_setting": {
                "sample_rate": self._sample_rate,
                "bitrate": 128000,
                "format": self._audio_format,
                "channel": 1,
            },
        }
        if self._language_boost:
            payload["language_boost"] = self._language_boost
        return payload

    async def _expect_event(
        self, ws: ClientWebSocketResponse, expected: str, phase: str
    ) -> None:
        """Read until we get the expected event, raising on error/timeout."""
        msg = await ws.receive()
        if msg.type == WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
            except (TypeError, ValueError) as err:
                _LOGGER.debug(
                    "MiniMax TTS WS %s: invalid JSON in msg: %r", phase, msg.data
                )
                raise HomeAssistantError(
                    f"MiniMax TTS WebSocket returned invalid JSON during {phase}: {err}"
                ) from err
        elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
            _LOGGER.debug("MiniMax TTS WS %s: socket closed (%s)", phase, msg.type)
            raise HomeAssistantError(
                f"MiniMax TTS WebSocket closed unexpectedly during {phase}"
            )
        else:
            _LOGGER.debug("MiniMax TTS WS %s: unexpected msg type %s", phase, msg.type)
            raise HomeAssistantError(
                f"MiniMax TTS WebSocket returned {msg.type} during {phase}"
            )

        _LOGGER.debug("MiniMax TTS WS %s: received %s", phase, data.get("event"))
        event = data.get("event")
        if event == self._EVENT_TASK_ERROR:
            raise HomeAssistantError(
                f"MiniMax TTS error during {phase}: {data.get('base_resp', data)}"
            )
        if event != expected:
            raise HomeAssistantError(
                f"MiniMax TTS expected {expected} during {phase}, got {event}"
            )

    async def _read_loop(
        self,
        ws: ClientWebSocketResponse,
        queue: asyncio.Queue[bytes | None],
    ) -> None:
        """Background task: read WS messages and push audio to the queue."""
        audio_chunks = 0
        audio_bytes = 0
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    _LOGGER.debug("MiniMax TTS WS read: non-text msg type=%s", msg.type)
                    break
                (
                    should_break,
                    chunks_added,
                    bytes_added,
                ) = await self._handle_read_message(msg.data, queue)
                audio_chunks += chunks_added
                audio_bytes += bytes_added
                if should_break:
                    break
        except ClientError as err:
            _LOGGER.debug("MiniMax TTS WebSocket read error: %s", err)
        finally:
            _LOGGER.debug(
                "MiniMax TTS WS read done: %d chunk(s), %d byte(s)",
                audio_chunks,
                audio_bytes,
            )
            await queue.put(None)

    async def _handle_read_message(
        self,
        raw: str,
        queue: asyncio.Queue[bytes | None],
    ) -> tuple[bool, int, int]:
        """Process a single TEXT message.

        Returns ``(should_break, audio_chunks_added, audio_bytes_added)``.
        """
        data = self._safe_parse_json(raw)
        if data is None:
            return False, 0, 0
        if data.get("event") == self._EVENT_TASK_ERROR:
            _LOGGER.error("MiniMax TTS task_error: %s", data)
            return True, 0, 0

        audio_hex = (data.get("data") or {}).get("audio") or ""
        chunks_added, bytes_added = 0, 0
        if audio_hex:
            chunk = self._decode_audio_chunk(audio_hex)
            if chunk is not None:
                chunks_added = 1
                bytes_added = len(chunk)
                await queue.put(chunk)

        if data.get("is_final") or data.get("event") == self._EVENT_TASK_FINISHED:
            _LOGGER.debug(
                "MiniMax TTS WS read: stream end (event=%s is_final=%s)",
                data.get("event"),
                data.get("is_final"),
            )
            return True, chunks_added, bytes_added
        return False, chunks_added, bytes_added

    @staticmethod
    def _safe_parse_json(raw: str) -> dict | None:
        """Parse a WebSocket text frame as JSON, logging and returning None on error."""
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            _LOGGER.debug("MiniMax TTS WS read: skipping invalid JSON: %r", raw)
            return None

    @staticmethod
    def _decode_audio_chunk(audio_hex: str) -> bytes | None:
        """Decode a hex-encoded audio payload, returning None if the hex is bad."""
        try:
            return bytes.fromhex(audio_hex)
        except (TypeError, ValueError):
            _LOGGER.debug("MiniMax TTS WS read: bad audio hex (len=%d)", len(audio_hex))
            return None

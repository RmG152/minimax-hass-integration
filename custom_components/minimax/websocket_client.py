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

            await ws.send_json(self._build_start_payload())
            await self._expect_event(ws, self._EVENT_TASK_STARTED, "task_start")

            read_task = asyncio.create_task(
                self._read_loop(ws, queue), name="minimax_t2a_ws_read"
            )

            async for text_chunk in text_chunks:
                if not text_chunk:
                    continue
                await ws.send_json({"event": "task_continue", "text": text_chunk})

            with contextlib.suppress(ConnectionResetError, ClientError, RuntimeError):
                await ws.send_json({"event": "task_finish"})

            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk

        except ClientError as err:
            raise HomeAssistantError(f"MiniMax TTS WebSocket error: {err}") from err
        finally:
            if read_task is not None and not read_task.done():
                read_task.cancel()
            if read_task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await read_task
            if ws is not None and not ws.closed:
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
                raise HomeAssistantError(
                    f"MiniMax TTS WebSocket returned invalid JSON during {phase}: {err}"
                ) from err
        elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
            raise HomeAssistantError(
                f"MiniMax TTS WebSocket closed unexpectedly during {phase}"
            )
        else:
            raise HomeAssistantError(
                f"MiniMax TTS WebSocket returned {msg.type} during {phase}"
            )

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
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    break
                try:
                    data = json.loads(msg.data)
                except (TypeError, ValueError):
                    continue
                if data.get("event") == self._EVENT_TASK_ERROR:
                    _LOGGER.error("MiniMax TTS task_error: %s", data)
                    break
                audio_hex = (data.get("data") or {}).get("audio")
                if audio_hex:
                    with contextlib.suppress(ValueError, TypeError):
                        await queue.put(bytes.fromhex(audio_hex))
                if (
                    data.get("is_final")
                    or data.get("event") == self._EVENT_TASK_FINISHED
                ):
                    break
        except ClientError as err:
            _LOGGER.debug("MiniMax TTS WebSocket read error: %s", err)
        finally:
            await queue.put(None)

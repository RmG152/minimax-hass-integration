"""MiniMax API client."""

import asyncio
import base64
import logging
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientSession
import anthropic
import httpx

from homeassistant.util.ssl import client_context

from .const import (
    MINIMAX_ANTHROPIC_API_URL,
    MINIMAX_IMAGE_API,
    MINIMAX_STT_API,
    MINIMAX_TTS_API,
)

TIMEOUT = 60
TTS_TIMEOUT = 60
STT_TIMEOUT = 60
IMAGE_TIMEOUT = 120
IMAGE_FETCH_TIMEOUT = 30
AI_TASK_TIMEOUT = 120
MINIMAX_DOMAINS = ["api.minimax.io", "cdn.minimax.io", "minimax.io"]

_LOGGER = logging.getLogger(__name__)


class MiniMaxApiClientError(Exception):
    """General MiniMaxApiClient error."""


class MiniMaxApiClient:
    """MiniMax API client."""

    def __init__(
        self,
        api_key: str,
        session: ClientSession,
    ) -> None:
        """Construct API client."""
        self._api_key = api_key
        self._session = session
        self._anthropic = anthropic.AsyncAnthropic(
            api_key=api_key,
            base_url=MINIMAX_ANTHROPIC_API_URL.rsplit("/v1", 1)[0],
            http_client=httpx.AsyncClient(
                verify=client_context(),
                timeout=httpx.Timeout(AI_TASK_TIMEOUT),
            ),
        )

    async def async_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system_prompt: str,
        max_tokens: int = 1024,
        tools: list[dict[str, Any]] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send chat request using Anthropic SDK."""
        try:
            kwargs: dict[str, Any] = {}
            if timeout is not None:
                kwargs["timeout"] = timeout
            response = await self._anthropic.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                tools=tools,
                **kwargs,
            )

            content_blocks = response.content
            text_parts = []
            tool_calls = []
            content = []

            for block in content_blocks:
                if block.type == "text":
                    text_parts.append(block.text)
                    content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
                    content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
                elif block.type == "thinking":
                    pass

            return {
                "success": True,
                "content": content,
                "text": "\n".join(text_parts) if text_parts else "",
                "tool_calls": tool_calls,
                "stop_reason": response.stop_reason,
            }

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Anthropic API error: %s", err)
            return {
                "success": False,
                "error": str(err)[:200],
            }

    async def async_tts(
        self,
        text: str,
        voice_id: str,
        speed: float,
        vol: float,
        pitch: int,
        model: str,
        language_boost: str | None = None,
    ) -> bytes:
        """Generate TTS audio using MiniMax API."""
        try:
            payload: dict[str, Any] = {
                "model": model,
                "text": text,
                "stream": False,
                "voice_setting": {
                    "voice_id": voice_id,
                    "speed": speed,
                    "vol": vol,
                    "pitch": pitch,
                },
            }
            if language_boost:
                payload["language_boost"] = language_boost

            async with asyncio.timeout(TTS_TIMEOUT):
                response = await self._session.post(
                    MINIMAX_TTS_API,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                result = await response.json()

                audio_hex = result.get("data", {}).get("audio", "")
                if audio_hex:
                    return bytes.fromhex(audio_hex)

                _LOGGER.error("No audio data in TTS response")
                raise MiniMaxApiClientError("No audio data in response")  # noqa: TRY301

        except Exception as err:
            _LOGGER.error("TTS API error: %s", err)
            raise MiniMaxApiClientError(str(err)) from err

    async def async_stt(
        self,
        audio_data: bytes,
        model: str,
        language: str,
        prompt: str,
        audio_format: str,
    ) -> str:
        """Transcribe audio using MiniMax STT API."""
        try:
            async with asyncio.timeout(STT_TIMEOUT):
                form_data = {
                    "file": ("audio.wav", audio_data, f"audio/{audio_format}"),
                    "model": (None, model),
                    "language": (None, language),
                    "prompt": (None, prompt),
                }

                response = await self._session.post(
                    MINIMAX_STT_API,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    data=form_data,
                )
                response.raise_for_status()
                result = await response.json()

                text = result.get("text", "")
                if text:
                    return text

                _LOGGER.warning("STT returned empty text")
                raise MiniMaxApiClientError("STT returned empty text")  # noqa: TRY301

        except Exception as err:
            _LOGGER.error("STT API error: %s", err)
            raise MiniMaxApiClientError(str(err)) from err

    async def async_image_generation(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        response_format: str = "base64",
    ) -> bytes:
        """Generate image using MiniMax API."""
        try:
            async with asyncio.timeout(IMAGE_TIMEOUT):
                response = await self._session.post(
                    MINIMAX_IMAGE_API,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "prompt": prompt,
                        "aspect_ratio": aspect_ratio,
                        "response_format": response_format,
                    },
                )
                response.raise_for_status()
                result = await response.json()

                if response_format == "base64":
                    image_data = result.get("data", {}).get("image_base64", [])
                    if image_data:
                        return base64.b64decode(image_data[0])
                else:
                    image_urls = result.get("data", {}).get("image_urls", [])
                    if image_urls:
                        url = image_urls[0]
                        parsed = urlparse(url)
                        if (
                            parsed.scheme != "https"
                            or parsed.netloc not in MINIMAX_DOMAINS
                        ):
                            _LOGGER.error("Untrusted image URL: %s", url)
                            raise MiniMaxApiClientError(  # noqa: TRY301
                                "Untrusted image URL"
                            )
                        async with httpx.AsyncClient(
                            verify=client_context(),
                            timeout=httpx.Timeout(IMAGE_FETCH_TIMEOUT),
                        ) as client:
                            img_resp = await client.get(url)
                            img_resp.raise_for_status()
                            return img_resp.content

                _LOGGER.error("No image data in response")
                raise MiniMaxApiClientError("No image data in response")  # noqa: TRY301

        except Exception as err:
            _LOGGER.error("Image generation API error: %s", err)
            raise MiniMaxApiClientError(str(err)) from err

    async def async_verify_connection(self) -> bool:
        """Verify API connection with a simple test call."""
        result = await self.async_chat(
            model="MiniMax-M2.7",
            messages=[{"role": "user", "content": "Hi"}],
            system_prompt="",
            max_tokens=5,
        )
        if not result.get("success", False):
            error = result.get("error", "")
            if (
                "401" in error
                or "authentication" in error.lower()
                or "api_key" in error.lower()
            ):
                raise MiniMaxApiClientError("Invalid API key")
            raise MiniMaxApiClientError(f"Connection failed: {error}")
        return True

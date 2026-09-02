from __future__ import annotations

import base64
import io
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from .config import settings


class VLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise VLMError("Vision model returned an empty response (no JSON content)")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        preview = text[:400].replace("\n", " ")
        raise VLMError(f"Vision model returned non-JSON. Preview: {preview!r}")


def encode_image_for_vlm(source: str | Path | bytes, *, max_side: int | None = None, quality: int = 85) -> tuple[str, str]:
    """Return (data URL, raw base64) resized so local VLMs do not blow the context window."""
    max_side = max_side or settings.vlm_image_max_side
    raw: bytes
    if isinstance(source, bytes):
        raw = source
    elif isinstance(source, str) and source.startswith("data:image"):
        raw = base64.b64decode(source.split(",", 1)[1])
    else:
        raw = Path(source).read_bytes()

    with Image.open(io.BytesIO(raw)) as img:
        img = img.convert("RGB")
        width, height = img.size
        longest = max(width, height)
        if longest > max_side:
            scale = max_side / longest
            img = img.resize(
                (max(1, int(width * scale)), max(1, int(height * scale))),
                Image.Resampling.LANCZOS,
            )
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}", encoded


def _message_text(message: Any) -> str:
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts: list[str] = []
        for item in message:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "".join(parts)
    if isinstance(message, dict):
        return _message_text(message.get("content"))
    return str(message)


class OpenAICompatibleVLM:
    def __init__(self):
        self.base_url = settings.vlm_base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/chat/completions"
        timeout = httpx.Timeout(
            connect=30.0,
            read=float(max(60, settings.vlm_timeout_seconds)),
            write=120.0,
            pool=30.0,
        )
        self.client = httpx.Client(timeout=timeout)

    def _is_ollama(self) -> bool:
        return ":11434" in self.base_url

    def _max_tokens(self) -> int:
        tokens = settings.vlm_max_tokens
        if self._is_ollama():
            return min(tokens, 4096)
        return tokens

    def chat_json(self, system: str, prompt: str, image_data_urls: list[str] | None = None) -> dict[str, Any]:
        sources = image_data_urls or []
        last_error: Exception | None = None
        sides = [settings.vlm_image_max_side]
        if settings.vlm_image_max_side > 896:
            sides.append(896)

        for attempt, max_side in enumerate(sides, start=1):
            prepared = [encode_image_for_vlm(src, max_side=max_side) for src in sources]
            data_urls = [item[0] for item in prepared]
            image_b64 = [item[1] for item in prepared]
            try:
                return self._chat_openai(system, prompt, data_urls)
            except (httpx.HTTPError, VLMError, json.JSONDecodeError) as exc:
                last_error = exc
                timed_out = isinstance(exc, httpx.TimeoutException) or "timed out" in str(exc).lower()
                empty = "empty" in str(exc).lower() or "non-JSON" in str(exc)
                if empty and self._is_ollama() and not timed_out:
                    try:
                        return self._chat_ollama_native(system, prompt, image_b64)
                    except (httpx.HTTPError, VLMError, json.JSONDecodeError) as native_exc:
                        last_error = native_exc
                if attempt >= len(sides):
                    break
                time.sleep(min(2 ** (attempt - 1), 10))

        assert last_error is not None
        raise last_error

    def _chat_openai(self, system: str, prompt: str, data_urls: list[str]) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for url in data_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})

        payload: dict[str, Any] = {
            "model": settings.vlm_model,
            "temperature": settings.vlm_temperature,
            "max_tokens": self._max_tokens(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
        }

        headers = {"Content-Type": "application/json"}
        if settings.vlm_api_key:
            headers["Authorization"] = f"Bearer {settings.vlm_api_key}"

        last_error: Exception | None = None
        for attempt in range(1, settings.max_retries + 1):
            try:
                response = self.client.post(self.endpoint, json=payload, headers=headers)
                if response.status_code >= 400:
                    raise VLMError(f"VLM HTTP {response.status_code}: {response.text[:1000]}")

                data = response.json()
                try:
                    message = data["choices"][0]["message"]
                except Exception as exc:
                    raise VLMError(f"Unexpected VLM response: {data}") from exc

                text = _message_text(message)
                if not text.strip():
                    choice = data["choices"][0]
                    raise VLMError(
                        "Vision model returned empty content "
                        f"(finish_reason={choice.get('finish_reason')!r}, model={data.get('model')!r})"
                    )
                return _extract_json(text)
            except (httpx.HTTPError, VLMError, json.JSONDecodeError) as exc:
                last_error = exc
                if isinstance(exc, httpx.TimeoutException):
                    raise VLMError(
                        f"Vision model timed out after {settings.vlm_timeout_seconds}s. "
                        "The Ollama 500 after 4m is the client closing the connection."
                    ) from exc
                if isinstance(exc, VLMError) and ("empty" in str(exc).lower() or "non-JSON" in str(exc)):
                    break
                if attempt >= settings.max_retries:
                    break
                time.sleep(min(2 ** (attempt - 1), 10))

        assert last_error is not None
        raise last_error

    def _chat_ollama_native(self, system: str, prompt: str, image_b64: list[str]) -> dict[str, Any]:
        root = self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url
        payload = {
            "model": settings.vlm_model,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": settings.vlm_temperature,
                "num_predict": self._max_tokens(),
                "num_ctx": settings.vlm_num_ctx,
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt, "images": image_b64},
            ],
        }
        response = self.client.post(f"{root}/api/chat", json=payload)
        if response.status_code >= 400:
            raise VLMError(f"Ollama HTTP {response.status_code}: {response.text[:1000]}")
        data = response.json()
        text = _message_text(data.get("message"))
        if not text.strip():
            raise VLMError(f"Ollama returned empty content: {data}")
        return _extract_json(text)

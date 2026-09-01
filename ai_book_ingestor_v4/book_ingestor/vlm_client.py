from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from .config import settings


class VLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


class OpenAICompatibleVLM:
    def __init__(self):
        self.base_url = settings.vlm_base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/chat/completions"
        self.client = httpx.Client(timeout=settings.vlm_timeout_seconds)

    def chat_json(self, system: str, prompt: str, image_data_urls: list[str] | None = None) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for url in image_data_urls or []:
            content.append({"type": "image_url", "image_url": {"url": url}})

        payload: dict[str, Any] = {
            "model": settings.vlm_model,
            "temperature": settings.vlm_temperature,
            "max_tokens": settings.vlm_max_tokens,
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
                    message = data["choices"][0]["message"]["content"]
                except Exception as exc:
                    raise VLMError(f"Unexpected VLM response: {data}") from exc

                if isinstance(message, list):
                    message = "".join(x.get("text", "") for x in message if isinstance(x, dict))
                return _extract_json(str(message))
            except (httpx.HTTPError, VLMError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= settings.max_retries:
                    break
                time.sleep(min(2 ** (attempt - 1), 10))

        assert last_error is not None
        raise last_error

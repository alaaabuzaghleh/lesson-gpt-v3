from __future__ import annotations

import os
import time
from pathlib import Path

from .config import Settings
from .page_prompt import build_page_prompt, build_system_prompt


class LocalVLMError(RuntimeError):
    pass


def _apply_vlm_env(settings: Settings) -> None:
    os.environ["VLM_BASE_URL"] = settings.vlm_base_url
    os.environ["VLM_API_KEY"] = settings.vlm_api_key
    os.environ["VLM_MODEL"] = settings.vlm_model
    os.environ["VLM_TIMEOUT_SECONDS"] = str(settings.vlm_timeout_seconds)
    os.environ["VLM_MAX_TOKENS"] = str(settings.vlm_max_tokens)
    os.environ["VLM_TEMPERATURE"] = str(settings.vlm_temperature)
    os.environ["VLM_IMAGE_MAX_SIDE"] = str(settings.vlm_image_max_side)
    os.environ["VLM_NUM_CTX"] = str(settings.vlm_num_ctx)
    os.environ["MAX_RETRIES"] = str(settings.vlm_max_retries)


class LocalVLMRunner:
    """Extract pages with a local vision model (Ollama qwen2.5vl, etc.)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.page_schema.is_file():
            raise FileNotFoundError(f"Output schema not found: {settings.page_schema}")
        self.schema_text = settings.page_schema.read_text(encoding="utf-8")
        _apply_vlm_env(settings)
        from book_ingestor.vlm_client import OpenAICompatibleVLM, VLMError

        self._vlm_error = VLMError
        self.vlm = OpenAICompatibleVLM()

    def extract_page(
        self,
        *,
        page_number: int,
        image_path: Path,
        work_dir: Path,
        language_hint: str = "Arabic and English textbook content",
    ) -> dict:
        del work_dir
        prompt = build_page_prompt(page_number=page_number, language_hint=language_hint)
        system = build_system_prompt(self.schema_text)
        last_error = ""
        for attempt in range(1, self.settings.vlm_max_retries + 1):
            try:
                data = self.vlm.chat_json(system, prompt, [str(image_path)])
                data.setdefault("pdf_page_number", page_number)
                return data
            except self._vlm_error as exc:
                last_error = str(exc)
                if attempt >= self.settings.vlm_max_retries:
                    break
                delay = min(5 * attempt, 30)
                print(
                    f"Local VLM error on page {page_number} "
                    f"(attempt {attempt}/{self.settings.vlm_max_retries}). "
                    f"Waiting {delay}s..."
                )
                time.sleep(delay)
        raise LocalVLMError(
            f"Local VLM failed for page {page_number} after {self.settings.vlm_max_retries} retries.\n{last_error}"
        )

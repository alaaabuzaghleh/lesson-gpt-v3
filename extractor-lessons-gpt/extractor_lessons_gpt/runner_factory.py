from __future__ import annotations

from .codex_runner import CodexRunner
from .config import Settings
from .local_vlm_runner import LocalVLMRunner


def make_page_runner(settings: Settings, backend: str):
    normalized = (backend or settings.extractor_backend).strip().lower()
    if normalized == "local":
        return LocalVLMRunner(settings), "local_vlm"
    if normalized == "codex":
        return CodexRunner(settings), "codex"
    raise ValueError(f"Unknown extractor backend: {backend!r}. Use 'local' or 'codex'.")

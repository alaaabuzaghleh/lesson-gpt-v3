from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REMOTE_ROOT = PROJECT_ROOT.parent / "remote-lessons-gpt"
DEFAULT_CODEX_BIN = "/Applications/ChatGPT.app/Contents/Resources/codex"
DEFAULT_SCHEMA = PROJECT_ROOT / "schemas" / "page_extraction.schema.json"

for env_file in (PROJECT_ROOT / ".env", REMOTE_ROOT / ".env", REMOTE_ROOT / ".env.use"):
    if env_file.is_file():
        load_dotenv(env_file, override=False)

if str(REMOTE_ROOT) not in sys.path:
    sys.path.insert(0, str(REMOTE_ROOT))


@dataclass(frozen=True)
class Settings:
    codex_bin: Path
    codex_model: str | None
    render_dpi: int
    output_dir: Path
    page_schema: Path
    extractor_backend: str
    remote_api_url: str
    codex_page_delay_seconds: float
    codex_max_retries: int
    codex_retry_base_seconds: float
    codex_retry_max_seconds: float
    vlm_base_url: str
    vlm_api_key: str
    vlm_model: str
    vlm_timeout_seconds: int
    vlm_max_tokens: int
    vlm_temperature: float
    vlm_image_max_side: int
    vlm_num_ctx: int
    vlm_max_retries: int
    local_page_delay_seconds: float
    api_host: str
    api_port: int
    api_data_root: Path
    api_worker_count: int
    api_worker_poll_seconds: float
    api_max_upload_mb: int
    api_cors_origins: str

    @classmethod
    def load(cls) -> Settings:
        codex_bin = Path(os.getenv("CODEX_BIN", DEFAULT_CODEX_BIN)).expanduser()
        model = os.getenv("CODEX_MODEL", "").strip() or None
        render_dpi = int(os.getenv("RENDER_DPI", "180"))
        output_dir = Path(os.getenv("OUTPUT_DIR", "./output")).expanduser()
        page_schema = Path(os.getenv("PAGE_SCHEMA", str(DEFAULT_SCHEMA))).expanduser()
        return cls(
            codex_bin=codex_bin,
            codex_model=model,
            render_dpi=render_dpi,
            output_dir=output_dir,
            page_schema=page_schema,
            extractor_backend=os.getenv("EXTRACTOR_BACKEND", "local").strip().lower(),
            remote_api_url=os.getenv("REMOTE_API_URL", "").strip(),
            codex_page_delay_seconds=float(os.getenv("CODEX_PAGE_DELAY_SECONDS", "12")),
            codex_max_retries=int(os.getenv("CODEX_MAX_RETRIES", "12")),
            codex_retry_base_seconds=float(os.getenv("CODEX_RETRY_BASE_SECONDS", "30")),
            codex_retry_max_seconds=float(os.getenv("CODEX_RETRY_MAX_SECONDS", "600")),
            vlm_base_url=os.getenv("VLM_BASE_URL", "http://localhost:11434/v1"),
            vlm_api_key=os.getenv("VLM_API_KEY", "EMPTY"),
            vlm_model=os.getenv("VLM_MODEL", "qwen2.5vl:7b"),
            vlm_timeout_seconds=int(os.getenv("VLM_TIMEOUT_SECONDS", "600")),
            vlm_max_tokens=int(os.getenv("VLM_MAX_TOKENS", "9000")),
            vlm_temperature=float(os.getenv("VLM_TEMPERATURE", "0")),
            vlm_image_max_side=int(os.getenv("VLM_IMAGE_MAX_SIDE", "1280")),
            vlm_num_ctx=int(os.getenv("VLM_NUM_CTX", "16384")),
            vlm_max_retries=int(os.getenv("VLM_MAX_RETRIES", "3")),
            local_page_delay_seconds=float(os.getenv("LOCAL_PAGE_DELAY_SECONDS", "2")),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8080")),
            api_data_root=Path(os.getenv("API_DATA_ROOT", "./data")).expanduser(),
            api_worker_count=int(os.getenv("API_WORKER_COUNT", "1")),
            api_worker_poll_seconds=float(os.getenv("API_WORKER_POLL_SECONDS", "0.5")),
            api_max_upload_mb=int(os.getenv("API_MAX_UPLOAD_MB", "1024")),
            api_cors_origins=os.getenv("API_CORS_ORIGINS", "*"),
        )


settings = Settings.load()

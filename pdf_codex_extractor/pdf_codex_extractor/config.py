from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INGESTOR_ROOT = PROJECT_ROOT.parent / "ai_book_ingestor_v4"
DEFAULT_CODEX_BIN = "/Applications/ChatGPT.app/Contents/Resources/codex"
DEFAULT_SCHEMA = PROJECT_ROOT / "schemas" / "page_extraction.schema.json"

for env_file in (PROJECT_ROOT / ".env", INGESTOR_ROOT / ".env", INGESTOR_ROOT / ".env.use"):
    if env_file.is_file():
        load_dotenv(env_file, override=False)

if str(INGESTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(INGESTOR_ROOT))


@dataclass(frozen=True)
class Settings:
    codex_bin: Path
    codex_model: str | None
    render_dpi: int
    output_dir: Path
    page_schema: Path
    opensearch_url: str
    opensearch_username: str
    opensearch_password: str
    opensearch_verify_certs: bool
    opensearch_index: str
    index_to_opensearch: bool
    extractor_backend: str
    remote_opensearch_url: str
    remote_opensearch_username: str
    remote_opensearch_password: str
    remote_opensearch_verify_certs: bool
    remote_opensearch_index: str
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
            opensearch_url=os.getenv("OPENSEARCH_URL", "http://localhost:9200"),
            opensearch_username=os.getenv("OPENSEARCH_USERNAME", ""),
            opensearch_password=os.getenv("OPENSEARCH_PASSWORD", ""),
            opensearch_verify_certs=os.getenv("OPENSEARCH_VERIFY_CERTS", "false").lower() == "true",
            opensearch_index=os.getenv("OPENSEARCH_INDEX", "school_book_content_v3"),
            index_to_opensearch=os.getenv("INDEX_TO_OPENSEARCH", "true").lower() == "true",
            extractor_backend=os.getenv("EXTRACTOR_BACKEND", "local").strip().lower(),
            remote_opensearch_url=os.getenv("REMOTE_OPENSEARCH_URL", ""),
            remote_opensearch_username=os.getenv("REMOTE_OPENSEARCH_USERNAME", ""),
            remote_opensearch_password=os.getenv("REMOTE_OPENSEARCH_PASSWORD", ""),
            remote_opensearch_verify_certs=os.getenv("REMOTE_OPENSEARCH_VERIFY_CERTS", "false").lower() == "true",
            remote_opensearch_index=os.getenv("REMOTE_OPENSEARCH_INDEX", os.getenv("OPENSEARCH_INDEX", "school_book_content_v3")),
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
        )


settings = Settings.load()

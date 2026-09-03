from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    vlm_base_url: str = "http://localhost:8000/v1"
    vlm_api_key: str = "EMPTY"
    vlm_model: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    vlm_timeout_seconds: int = 600
    vlm_max_tokens: int = 9000
    vlm_temperature: float = 0.0
    vlm_image_max_side: int = 1280
    vlm_num_ctx: int = 16384

    opensearch_url: str = "http://localhost:9200"
    opensearch_username: str = ""
    opensearch_password: str = ""
    opensearch_verify_certs: bool = False
    opensearch_index: str = "school_book_content_v3"

    render_dpi: int = 220
    visual_crop_padding_px: int = 12
    max_retries: int = 3
    max_visual_retries: int = 2
    save_page_images: bool = True
    save_visual_crops: bool = True
    deep_visual_analysis: bool = True
    verify_visual_analysis: bool = True
    include_neighbor_page_text: bool = True
    visual_context_chars: int = 10000

    # MinerU document parser: https://github.com/opendatalab/mineru
    # pipeline backend is CPU/MPS friendly and uses a dedicated Arabic OCR model.
    mineru_enabled: bool = True
    mineru_required: bool = False
    mineru_api_url: str = ""
    mineru_backend: str = "pipeline"
    mineru_parse_method: str = "auto"
    mineru_language: str = "arabic"
    mineru_effort: str = "medium"
    mineru_formula_enable: bool = True
    mineru_table_enable: bool = True
    mineru_image_analysis: bool = True
    mineru_timeout_seconds: int = 3600
    mineru_poll_seconds: float = 2.0
    mineru_model_source: str = ""
    mineru_text_chars: int = 16000
    ocr_min_chars: int = 20
    ocr_retry_empty: bool = True
    vlm_page_extraction_enabled: bool = False

    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_data_root: str = "./data"
    api_worker_count: int = 2
    api_worker_poll_seconds: float = 0.5
    api_max_upload_mb: int = 1024
    api_cors_origins: str = "*"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/lessons_gpt"
    jwt_secret: str = "change-me-in-production-use-long-random-string"
    jwt_expire_minutes: int = 480
    super_admin_email: str = "superadmin@lessonsgpt.com"
    super_admin_password: str = "SuperAdmin123!"
    super_admin_name: str = "Super Admin"


settings = Settings()

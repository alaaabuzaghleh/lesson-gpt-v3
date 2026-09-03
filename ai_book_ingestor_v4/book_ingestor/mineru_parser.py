from __future__ import annotations

import io
import json
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urljoin

import httpx
from rich.console import Console

from .config import settings
from .normalizer import looks_like_visual_arabic, restore_arabic_logical_order

console = Console()

ProgressFn = Callable[[str], None]

CONTENT_LIST_SUFFIX = "_content_list.json"
CONTENT_LIST_V2_SUFFIX = "_content_list_v2.json"
MIDDLE_JSON_SUFFIX = "_middle.json"


class MinerUError(RuntimeError):
    """Raised when MinerU parsing is required but cannot be completed."""


@dataclass
class MinerUBlock:
    type: str
    text: str
    bbox: list[int] | None = None
    page_idx: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def as_prompt_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.type, "text": self.text}
        if self.bbox:
            data["bbox"] = self.bbox
        if self.extra:
            data.update(self.extra)
        return data


@dataclass
class MinerUPage:
    pdf_page_number: int
    blocks: list[MinerUBlock] = field(default_factory=list)

    @property
    def text(self) -> str:
        return format_mineru_page_text(self.blocks)


@dataclass
class MinerUDocument:
    pages: dict[int, MinerUPage] = field(default_factory=dict)
    source: str = "mineru"
    output_dir: Path | None = None
    backend: str = "pipeline"
    language: str = "arabic"

    def page(self, pdf_page_number: int) -> MinerUPage | None:
        return self.pages.get(int(pdf_page_number))

    def covers(self, start_page: int, end_page: int) -> bool:
        if not self.pages:
            return False
        needed = set(range(start_page, end_page + 1))
        return needed.issubset(self.pages)

    def merge(self, other: "MinerUDocument") -> "MinerUDocument":
        self.pages.update(other.pages)
        if other.source:
            self.source = other.source
        if other.backend:
            self.backend = other.backend
        if other.language:
            self.language = other.language
        if other.output_dir:
            self.output_dir = other.output_dir
        return self


def mineru_ocr_language(value: str | None = None) -> str:
    """Map catalog/book language values onto MinerU pipeline OCR language keys."""
    raw = (value or settings.mineru_language or "arabic").strip().casefold()
    if raw in {"", "auto"}:
        return "arabic"
    compact = raw.replace(" ", "").replace("_", "-")
    arabic_aliases = {
        "ar",
        "arabic",
        "fa",
        "ur",
        "mixed",
        "ar,en",
        "en,ar",
        "ar-en",
        "en-ar",
        "arabic,english",
        "english,arabic",
    }
    if compact in arabic_aliases:
        return "arabic"
    if compact in {"en", "english", "latin", "ch", "zh", "chinese", "ja", "jp", "japanese"}:
        return "ch"
    return raw


def _join_captions(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def _span_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        children = value.get("children")
        if children:
            return _span_text(children)
        return str(value.get("content") or value.get("text") or "").strip()
    if isinstance(value, (list, tuple)):
        return " ".join(part for part in (_span_text(item) for item in value) if part)
    return str(value).strip()


def _normalize_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 4:
        return None
    try:
        coords = [int(round(float(v))) for v in value[:4]]
    except (TypeError, ValueError):
        return None
    # MinerU VLM model.json uses 0-1 percentages; content_list uses 0-1000.
    if all(0.0 <= float(v) <= 1.0 for v in value[:4]) and max(float(v) for v in value[:4]) <= 1.0:
        coords = [int(round(float(v) * 1000)) for v in value[:4]]
    return coords


def _block_text_from_content_list(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    typ = str(item.get("type") or "text").strip() or "text"
    extra: dict[str, Any] = {}
    if item.get("text_level") is not None:
        extra["text_level"] = item["text_level"]
    if item.get("sub_type"):
        extra["sub_type"] = item["sub_type"]

    if typ in {"text", "title", "list", "index", "code", "algorithm"}:
        text = str(item.get("text") or item.get("code_body") or item.get("algorithm_content") or "").strip()
        caption = _join_captions(item.get("code_caption") or item.get("algorithm_caption"))
        if caption:
            extra["caption"] = caption
            text = f"{caption}\n{text}".strip()
        return text, extra

    if typ == "equation":
        return str(item.get("text") or "").strip(), extra

    if typ == "table":
        caption = _join_captions(item.get("table_caption"))
        footnote = _join_captions(item.get("table_footnote"))
        body = str(item.get("table_body") or "").strip()
        if caption:
            extra["caption"] = caption
        if footnote:
            extra["footnote"] = footnote
        parts = [p for p in (caption, body, footnote) if p]
        return "\n".join(parts), extra

    if typ in {"image", "chart"}:
        caption = _join_captions(
            item.get("image_caption") or item.get("chart_caption") or item.get("image_footnote")
        )
        extra["caption"] = caption
        return caption or f"[{typ}]", extra

    return str(item.get("text") or _join_captions(item.get("content")) or "").strip(), extra


def _fix_mineru_arabic(pages: dict[int, MinerUPage]) -> dict[int, MinerUPage]:
    """Restore logical Arabic when MinerU/PaddleOCR stored visual LTR glyphs."""
    for page in pages.values():
        blob = "\n".join(
            part
            for block in page.blocks
            for part in (block.text, *(value for value in block.extra.values() if isinstance(value, str)))
            if part
        )
        force = looks_like_visual_arabic(blob)
        for block in page.blocks:
            block.text = restore_arabic_logical_order(block.text, force=force)
            for key, value in list(block.extra.items()):
                if isinstance(value, str) and value:
                    block.extra[key] = restore_arabic_logical_order(value, force=force)
    return pages


def parse_content_list(items: list[Any], *, page_offset: int = 0) -> dict[int, MinerUPage]:
    pages: dict[int, MinerUPage] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        page_idx = int(item.get("page_idx") or 0)
        pdf_page = page_idx + page_offset + 1
        text, extra = _block_text_from_content_list(item)
        block = MinerUBlock(
            type=str(item.get("type") or "text"),
            text=text,
            bbox=_normalize_bbox(item.get("bbox")),
            page_idx=page_idx,
            extra=extra,
        )
        page = pages.setdefault(pdf_page, MinerUPage(pdf_page_number=pdf_page))
        page.blocks.append(block)
    return _fix_mineru_arabic(pages)


def _content_v2_text(item: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    typ = str(item.get("type") or "paragraph")
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    extra: dict[str, Any] = {}
    if item.get("sub_type"):
        extra["sub_type"] = item["sub_type"]

    if typ == "title":
        return "title", _span_text(content.get("title_content")), extra
    if typ == "paragraph":
        return "text", _span_text(content.get("paragraph_content")), extra
    if typ == "equation_interline":
        math = content.get("math_content") or content.get("text") or ""
        return "equation", str(math).strip(), extra
    if typ == "table":
        caption = _span_text(content.get("table_caption") or content.get("caption"))
        body = str(content.get("table_body") or content.get("html") or "").strip()
        if caption:
            extra["caption"] = caption
        return "table", "\n".join(p for p in (caption, body) if p), extra
    if typ in {"image", "chart"}:
        caption = _span_text(
            content.get("image_caption") or content.get("chart_caption") or content.get("caption")
        )
        extra["caption"] = caption
        return typ, caption or f"[{typ}]", extra
    if typ in {"list", "index"}:
        return typ, _span_text(content.get("list_items") or content.get("items")), extra
    if typ.startswith("page_"):
        key = f"{typ}_content"
        return typ, _span_text(content.get(key) or content.get("content")), extra
    return typ, _span_text(content) or _span_text(item.get("text")), extra


def parse_content_list_v2(pages_data: list[Any], *, page_offset: int = 0) -> dict[int, MinerUPage]:
    pages: dict[int, MinerUPage] = {}
    for page_idx, items in enumerate(pages_data):
        if not isinstance(items, list):
            continue
        pdf_page = page_idx + page_offset + 1
        page = pages.setdefault(pdf_page, MinerUPage(pdf_page_number=pdf_page))
        for item in items:
            if not isinstance(item, dict):
                continue
            typ, text, extra = _content_v2_text(item)
            page.blocks.append(
                MinerUBlock(
                    type=typ,
                    text=text,
                    bbox=_normalize_bbox(item.get("bbox")),
                    page_idx=page_idx,
                    extra=extra,
                )
            )
    return _fix_mineru_arabic(pages)


def parse_middle_json(data: dict[str, Any], *, page_offset: int = 0) -> dict[int, MinerUPage]:
    pages: dict[int, MinerUPage] = {}
    for info in data.get("pdf_info") or []:
        if not isinstance(info, dict):
            continue
        page_idx = int(info.get("page_idx") or 0)
        pdf_page = page_idx + page_offset + 1
        page = pages.setdefault(pdf_page, MinerUPage(pdf_page_number=pdf_page))
        for block in info.get("para_blocks") or []:
            if not isinstance(block, dict):
                continue
            texts: list[str] = []
            for line in block.get("lines") or []:
                if not isinstance(line, dict):
                    continue
                for span in line.get("spans") or []:
                    if isinstance(span, dict) and span.get("content"):
                        texts.append(str(span["content"]).strip())
            text = " ".join(t for t in texts if t)
            if not text and block.get("type") in {"image", "table", "chart"}:
                text = f"[{block.get('type')}]"
            page.blocks.append(
                MinerUBlock(
                    type=str(block.get("type") or "text"),
                    text=text,
                    bbox=_normalize_bbox(block.get("bbox")),
                    page_idx=page_idx,
                )
            )
    return _fix_mineru_arabic(pages)


def format_mineru_page_text(blocks: Iterable[MinerUBlock]) -> str:
    lines: list[str] = []
    for block in blocks:
        typ = (block.type or "text").strip()
        text = (block.text or "").strip()
        if typ in {"page_header", "page_footer", "page_number", "header", "footer"}:
            continue
        if not text:
            continue
        if typ in {"title"} or block.extra.get("text_level"):
            level = int(block.extra.get("text_level") or 1)
            lines.append(f"{'#' * min(max(level, 1), 6)} {text}")
        elif typ == "equation":
            lines.append(text)
        elif typ == "table":
            lines.append(f"[table]\n{text}")
        elif typ in {"image", "chart"}:
            lines.append(f"[{typ}] {text}".rstrip())
        elif typ.startswith("page_"):
            continue
        else:
            lines.append(text)
    return "\n\n".join(lines).strip()


SKIP_MINERU_TYPES = {
    "page_header",
    "page_footer",
    "page_number",
    "header",
    "footer",
    "page_aside_text",
    "page_footnote",
}

MINERU_TYPE_TO_CONTENT = {
    "title": "section_heading",
    "text": "explanation",
    "paragraph": "explanation",
    "list": "explanation",
    "index": "index",
    "equation": "equation",
    "equation_interline": "equation",
    "table": "table",
    "image": "image",
    "chart": "chart",
    "code": "other",
    "algorithm": "other",
}


def mineru_block_is_indexable(block: MinerUBlock) -> bool:
    typ = (block.type or "").strip().casefold()
    if typ in SKIP_MINERU_TYPES or typ.startswith("page_"):
        return False
    return bool((block.text or "").strip())


def mineru_content_type(block: MinerUBlock) -> str:
    typ = (block.type or "text").strip().casefold()
    level = block.extra.get("text_level")
    if typ == "title" and level is not None:
        try:
            depth = int(level)
        except (TypeError, ValueError):
            depth = 1
        if depth <= 1:
            return "unit_title"
        if depth == 2:
            return "chapter_title"
        if depth == 3:
            return "lesson_title"
        return "section_heading"
    return MINERU_TYPE_TO_CONTENT.get(typ, "explanation")


def mineru_bbox_dict(block: MinerUBlock) -> dict[str, int] | None:
    if not block.bbox or len(block.bbox) < 4:
        return None
    x1, y1, x2, y2 = [max(0, min(1000, int(v))) for v in block.bbox[:4]]
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def format_mineru_blocks_for_prompt(blocks: Iterable[MinerUBlock], limit: int = 80) -> str:
    payload = []
    for idx, block in enumerate(list(blocks)[:limit], start=1):
        item = {"seq": idx, **block.as_prompt_dict()}
        if item.get("text") and len(item["text"]) > 1200:
            item["text"] = item["text"][:1200].rstrip() + "…"
        payload.append(item)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def mineru_page_artifact_dir(work_dir: str | Path, page_no: int) -> Path:
    return Path(work_dir) / "mineru_pages" / f"page_{int(page_no):04d}"


def load_incremental_mineru_document(work_dir: str | Path) -> MinerUDocument | None:
    """Rebuild a MinerU document from per-page caches, falling back to a whole-book cache."""
    work_dir = Path(work_dir)
    merged = MinerUDocument(source="mineru-cache", output_dir=work_dir / "mineru")
    pages_root = work_dir / "mineru_pages"
    if pages_root.exists():
        for folder in sorted(path for path in pages_root.glob("page_*") if path.is_dir()):
            meta_path = _cache_meta_path(folder)
            offset = 0
            if meta_path.exists():
                try:
                    offset = int(json.loads(meta_path.read_text(encoding="utf-8")).get("page_offset") or 0)
                except (json.JSONDecodeError, TypeError, ValueError):
                    offset = 0
            part = load_mineru_document(folder, page_offset=offset)
            if part and part.pages:
                merged.merge(part)

    legacy_dir = work_dir / "mineru"
    if legacy_dir.exists():
        meta_path = _cache_meta_path(legacy_dir)
        offset = 0
        if meta_path.exists():
            try:
                offset = int(json.loads(meta_path.read_text(encoding="utf-8")).get("page_offset") or 0)
            except (json.JSONDecodeError, TypeError, ValueError):
                offset = 0
        legacy = load_mineru_document(legacy_dir, page_offset=offset)
        if legacy:
            for page_no, page in legacy.pages.items():
                merged.pages.setdefault(page_no, page)
            if not merged.source or merged.source == "mineru-cache":
                merged.source = legacy.source or merged.source
            merged.backend = merged.backend or legacy.backend
            merged.language = merged.language or legacy.language

    return merged if merged.pages else None


def find_mineru_artifact(root: Path, suffix: str) -> Path | None:
    if not root.exists():
        return None
    matches = sorted(path for path in root.rglob(f"*{suffix}") if path.is_file())
    if not matches:
        return None
    # Prefer the shortest path so backend-method folders win over nested copies.
    matches.sort(key=lambda p: (len(p.parts), len(p.name), str(p)))
    return matches[0]


def load_mineru_document(output_dir: Path, *, page_offset: int = 0) -> MinerUDocument | None:
    content_list_path = find_mineru_artifact(output_dir, CONTENT_LIST_SUFFIX)
    if content_list_path and CONTENT_LIST_V2_SUFFIX not in content_list_path.name:
        items = json.loads(content_list_path.read_text(encoding="utf-8"))
        if isinstance(items, list):
            pages = parse_content_list(items, page_offset=page_offset)
            if pages:
                return MinerUDocument(pages=pages, output_dir=output_dir)

    v2_path = find_mineru_artifact(output_dir, CONTENT_LIST_V2_SUFFIX)
    if v2_path:
        items = json.loads(v2_path.read_text(encoding="utf-8"))
        if isinstance(items, list):
            pages = parse_content_list_v2(items, page_offset=page_offset)
            if pages:
                return MinerUDocument(pages=pages, output_dir=output_dir)

    middle_path = find_mineru_artifact(output_dir, MIDDLE_JSON_SUFFIX)
    if middle_path:
        data = json.loads(middle_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            pages = parse_middle_json(data, page_offset=page_offset)
            if pages:
                return MinerUDocument(pages=pages, output_dir=output_dir)
    return None


def _cache_meta_path(output_dir: Path) -> Path:
    return output_dir / "parse_meta.json"


def _pdf_fingerprint(pdf_path: Path) -> dict[str, Any]:
    stat = pdf_path.stat()
    return {"pdf_size": stat.st_size, "pdf_mtime": int(stat.st_mtime)}


def _parse_settings_fingerprint(start_page: int, end_page: int, language: str) -> dict[str, Any]:
    return {
        "backend": settings.mineru_backend,
        "parse_method": settings.mineru_parse_method,
        "language": language,
        "formula_enable": settings.mineru_formula_enable,
        "table_enable": settings.mineru_table_enable,
        "effort": settings.mineru_effort,
        "start_page": start_page,
        "end_page": end_page,
    }


def _cache_matches(
    output_dir: Path,
    pdf_path: Path,
    start_page: int,
    end_page: int,
    language: str,
) -> bool:
    path = _cache_meta_path(output_dir)
    if not path.exists():
        return False
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    expected = {**_pdf_fingerprint(pdf_path), **_parse_settings_fingerprint(start_page, end_page, language)}
    for key, value in expected.items():
        if key in {"start_page", "end_page"}:
            continue
        if cached.get(key) != value:
            return False
    cached_start = int(cached.get("start_page") or 1)
    cached_end = int(cached.get("end_page") or 0)
    return cached_start <= start_page and cached_end >= end_page


def _write_cache_meta(
    output_dir: Path,
    pdf_path: Path,
    start_page: int,
    end_page: int,
    language: str,
    source: str,
) -> None:
    payload = {
        **_pdf_fingerprint(pdf_path),
        **_parse_settings_fingerprint(start_page, end_page, language),
        "source": source,
        "page_offset": start_page - 1,
    }
    _cache_meta_path(output_dir).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _safe_extract_zip(zip_bytes: bytes, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    root = output_dir.resolve()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for member in archive.infolist():
            name = Path(member.filename)
            if name.is_absolute() or ".." in name.parts:
                raise MinerUError(f"Refusing unsafe MinerU ZIP entry: {member.filename}")
            target = (root / name).resolve()
            if target != root and root not in target.parents:
                raise MinerUError(f"Refusing unsafe MinerU ZIP entry: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))


def _abs_url(base_url: str, maybe_relative: str) -> str:
    if maybe_relative.startswith(("http://", "https://")):
        return maybe_relative
    return urljoin(base_url.rstrip("/") + "/", maybe_relative.lstrip("/"))


def _form_data(language: str, start_page_id: int, end_page_id: int | None) -> dict[str, Any]:
    return {
        "lang_list": language,
        "backend": settings.mineru_backend,
        "effort": settings.mineru_effort,
        "parse_method": settings.mineru_parse_method,
        "formula_enable": str(settings.mineru_formula_enable).lower(),
        "table_enable": str(settings.mineru_table_enable).lower(),
        "image_analysis": str(settings.mineru_image_analysis).lower(),
        "return_md": "true",
        "return_middle_json": "true",
        "return_model_output": "false",
        "return_content_list": "true",
        "return_images": "false",
        "response_format_zip": "true",
        "return_original_file": "false",
        "start_page_id": str(start_page_id),
        "end_page_id": str(99999 if end_page_id is None else end_page_id),
    }


def _http_timeout() -> httpx.Timeout:
    total = max(30, int(settings.mineru_timeout_seconds))
    return httpx.Timeout(total, connect=30.0, read=total, write=60.0)


def parse_via_http_api(
    pdf_path: Path,
    output_dir: Path,
    *,
    language: str,
    start_page: int,
    end_page: int,
    progress: ProgressFn | None = None,
) -> MinerUDocument:
    base_url = settings.mineru_api_url.rstrip("/")
    start_page_id = start_page - 1
    end_page_id = end_page - 1
    form = _form_data(language, start_page_id, end_page_id)
    timeout = _http_timeout()

    def emit(message: str) -> None:
        if progress:
            progress(message)

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        emit(f"Submitting PDF to MinerU API {base_url}")
        with pdf_path.open("rb") as handle:
            files = {"files": (pdf_path.name, handle, "application/pdf")}
            submitted = client.post(f"{base_url}/tasks", data=form, files=files)

        if submitted.status_code == 404:
            emit("MinerU /tasks not available; using synchronous /file_parse")
            with pdf_path.open("rb") as handle:
                files = {"files": (pdf_path.name, handle, "application/pdf")}
                parsed = client.post(f"{base_url}/file_parse", data=form, files=files)
            parsed.raise_for_status()
            _safe_extract_zip(parsed.content, output_dir)
        else:
            if submitted.status_code != 202:
                raise MinerUError(
                    f"MinerU task submit failed: {submitted.status_code} {submitted.text[:500]}"
                )
            payload = submitted.json()
            task_id = payload.get("task_id")
            status_url = _abs_url(base_url, str(payload.get("status_url") or f"/tasks/{task_id}"))
            result_url = _abs_url(base_url, str(payload.get("result_url") or f"/tasks/{task_id}/result"))
            deadline = time.monotonic() + max(30, int(settings.mineru_timeout_seconds))
            while time.monotonic() < deadline:
                status_resp = client.get(status_url)
                status_resp.raise_for_status()
                status_payload = status_resp.json()
                status = status_payload.get("status")
                queued = status_payload.get("queued_ahead")
                if queued is not None:
                    emit(f"MinerU task {status} (queued_ahead={queued})")
                else:
                    emit(f"MinerU task {status}")
                if status in {"pending", "processing"}:
                    time.sleep(max(0.5, settings.mineru_poll_seconds))
                    continue
                if status == "completed":
                    break
                raise MinerUError(f"MinerU task {task_id} failed: {json.dumps(status_payload, ensure_ascii=False)}")
            else:
                raise MinerUError(f"Timed out waiting for MinerU task {task_id}")

            result = client.get(result_url, timeout=_http_timeout())
            result.raise_for_status()
            _safe_extract_zip(result.content, output_dir)

    document = load_mineru_document(output_dir, page_offset=start_page_id)
    if document is None:
        raise MinerUError("MinerU API finished but no content_list/middle.json artifacts were found")
    document.source = "mineru-api"
    document.backend = settings.mineru_backend
    document.language = language
    document.output_dir = output_dir
    return document


def parse_via_python_api(
    pdf_path: Path,
    output_dir: Path,
    *,
    language: str,
    start_page: int,
    end_page: int,
) -> MinerUDocument:
    try:
        from mineru.cli.common import do_parse
    except ImportError as exc:
        raise MinerUError("mineru Python package is not installed") from exc

    if settings.mineru_model_source:
        import os

        os.environ.setdefault("MINERU_MODEL_SOURCE", settings.mineru_model_source)

    start_page_id = start_page - 1
    do_parse(
        output_dir=str(output_dir),
        pdf_file_names=[pdf_path.stem],
        pdf_bytes_list=[pdf_path.read_bytes()],
        p_lang_list=[language],
        backend=settings.mineru_backend,
        parse_method=settings.mineru_parse_method,
        formula_enable=settings.mineru_formula_enable,
        table_enable=settings.mineru_table_enable,
        start_page_id=start_page_id,
        end_page_id=end_page - 1,
        image_analysis=settings.mineru_image_analysis,
        effort=settings.mineru_effort,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
        f_dump_orig_pdf=False,
        f_dump_model_output=False,
        f_dump_md=True,
        f_dump_middle_json=True,
        f_dump_content_list=True,
    )
    document = load_mineru_document(output_dir, page_offset=start_page_id)
    if document is None:
        raise MinerUError("mineru.do_parse finished but no structured artifacts were found")
    document.source = "mineru-python"
    document.backend = settings.mineru_backend
    document.language = language
    return document


def parse_via_cli(
    pdf_path: Path,
    output_dir: Path,
    *,
    language: str,
    start_page: int,
    end_page: int,
) -> MinerUDocument:
    import shutil
    import subprocess

    mineru_bin = shutil.which("mineru")
    if not mineru_bin:
        raise MinerUError("mineru CLI is not on PATH")

    if settings.mineru_model_source:
        import os

        os.environ.setdefault("MINERU_MODEL_SOURCE", settings.mineru_model_source)

    start_page_id = start_page - 1
    command = [
        mineru_bin,
        "-p",
        str(pdf_path),
        "-o",
        str(output_dir),
        "-b",
        settings.mineru_backend,
        "-m",
        settings.mineru_parse_method,
        "-l",
        language,
        "--effort",
        settings.mineru_effort,
        "-f",
        str(settings.mineru_formula_enable).lower(),
        "-t",
        str(settings.mineru_table_enable).lower(),
        "-s",
        str(start_page_id),
        "-e",
        str(end_page - 1),
    ]
    if settings.mineru_api_url:
        command.extend(["--api-url", settings.mineru_api_url])
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(30, int(settings.mineru_timeout_seconds)),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[-800:]
        raise MinerUError(f"mineru CLI failed with exit {completed.returncode}: {detail}")
    document = load_mineru_document(output_dir, page_offset=start_page_id)
    if document is None:
        raise MinerUError("mineru CLI finished but no structured artifacts were found")
    document.source = "mineru-cli"
    document.backend = settings.mineru_backend
    document.language = language
    return document


def mineru_runtime_available() -> bool:
    if settings.mineru_api_url.strip():
        return True
    try:
        import importlib.util

        if importlib.util.find_spec("mineru") is not None:
            return True
    except Exception:
        pass
    import shutil

    return shutil.which("mineru") is not None


def parse_pdf_with_mineru(
    pdf_path: str | Path,
    work_dir: str | Path,
    *,
    start_page: int = 1,
    end_page: int | None = None,
    language: str | None = None,
    resume: bool = True,
    progress: ProgressFn | None = None,
    artifact_dir: str | Path | None = None,
) -> MinerUDocument:
    pdf_path = Path(pdf_path).resolve()
    output_dir = Path(artifact_dir) if artifact_dir is not None else Path(work_dir) / "mineru"
    output_dir.mkdir(parents=True, exist_ok=True)
    ocr_lang = mineru_ocr_language(language)
    resolved_end = int(end_page or 0)
    if resolved_end < start_page:
        raise ValueError("end_page must be greater than or equal to start_page")

    if resume and _cache_matches(output_dir, pdf_path, start_page, resolved_end, ocr_lang):
        for offset in (start_page - 1, 0):
            cached = load_mineru_document(output_dir, page_offset=offset)
            if cached and cached.pages:
                cached.source = "mineru-cache"
                cached.language = ocr_lang
                cached.backend = settings.mineru_backend
                if progress:
                    progress("Reusing cached MinerU parse")
                return cached

    errors: list[str] = []
    document: MinerUDocument | None = None
    source = ""

    if settings.mineru_api_url.strip():
        try:
            document = parse_via_http_api(
                pdf_path,
                output_dir,
                language=ocr_lang,
                start_page=start_page,
                end_page=resolved_end,
                progress=progress,
            )
            source = "mineru-api"
        except Exception as exc:
            errors.append(f"api:{exc}")

    if document is None:
        try:
            if progress:
                progress("Running local MinerU Python API")
            document = parse_via_python_api(
                pdf_path,
                output_dir,
                language=ocr_lang,
                start_page=start_page,
                end_page=resolved_end,
            )
            source = "mineru-python"
        except Exception as exc:
            errors.append(f"python:{exc}")

    if document is None:
        try:
            if progress:
                progress("Running MinerU CLI")
            document = parse_via_cli(
                pdf_path,
                output_dir,
                language=ocr_lang,
                start_page=start_page,
                end_page=resolved_end,
            )
            source = "mineru-cli"
        except Exception as exc:
            errors.append(f"cli:{exc}")

    if document is None:
        raise MinerUError(
            "MinerU parse failed. Install mineru, expose MINERU_API_URL, or disable MINERU_ENABLED. "
            + " | ".join(errors)
        )

    _write_cache_meta(output_dir, pdf_path, start_page, resolved_end, ocr_lang, source)
    return document

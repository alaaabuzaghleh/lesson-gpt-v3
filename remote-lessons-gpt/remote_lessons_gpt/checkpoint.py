from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHECKPOINT_FILENAME = "checkpoint.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unique_sorted(values: list[int]) -> list[int]:
    return sorted({int(v) for v in values})


@dataclass
class JobCheckpoint:
    """Durable per-job progress so extraction can stop and resume without losing work."""

    version: int = 1
    book_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    extracted_pages: list[int] = field(default_factory=list)
    indexed_pages: list[int] = field(default_factory=list)
    ocr_pages: list[int] = field(default_factory=list)
    mineru_pages: list[int] = field(default_factory=list)
    failed_pages: list[int] = field(default_factory=list)
    extracted_records: int = 0
    indexed_records: int = 0
    visual_assets: int = 0
    stage: str = "starting"
    current_page: int | None = None
    total_pages: int | None = None
    start_page: int = 1
    end_page: int | None = None
    updated_at: str | None = None

    def mark_extracted(self, page_no: int) -> None:
        if page_no not in self.extracted_pages:
            self.extracted_pages.append(int(page_no))
        self.extracted_pages = _unique_sorted(self.extracted_pages)

    def mark_indexed(self, page_no: int) -> None:
        self.mark_extracted(page_no)
        if page_no not in self.indexed_pages:
            self.indexed_pages.append(int(page_no))
        self.indexed_pages = _unique_sorted(self.indexed_pages)

    def mark_ocr(self, page_no: int) -> None:
        if page_no not in self.ocr_pages:
            self.ocr_pages.append(int(page_no))
        self.ocr_pages = _unique_sorted(self.ocr_pages)
        if page_no in self.failed_pages:
            self.failed_pages = [p for p in self.failed_pages if p != int(page_no)]

    def mark_mineru(self, page_no: int) -> None:
        if page_no not in self.mineru_pages:
            self.mineru_pages.append(int(page_no))
        self.mineru_pages = _unique_sorted(self.mineru_pages)

    def mark_failed(self, page_no: int) -> None:
        if page_no not in self.failed_pages:
            self.failed_pages.append(int(page_no))
        self.failed_pages = _unique_sorted(self.failed_pages)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["extracted_pages"] = _unique_sorted(self.extracted_pages)
        data["indexed_pages"] = _unique_sorted(self.indexed_pages)
        data["ocr_pages"] = _unique_sorted(self.ocr_pages)
        data["mineru_pages"] = _unique_sorted(self.mineru_pages)
        data["failed_pages"] = _unique_sorted(self.failed_pages)
        data["updated_at"] = _utcnow()
        return data

    def save(self, path: str | Path) -> dict[str, Any]:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        self.updated_at = payload["updated_at"]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> JobCheckpoint:
        if not data:
            return cls()
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        for key in ("extracted_pages", "indexed_pages", "ocr_pages", "mineru_pages", "failed_pages"):
            if key in known and known[key] is not None:
                known[key] = [int(v) for v in known[key]]
        return cls(**known)

    @classmethod
    def load(cls, path: str | Path) -> JobCheckpoint | None:
        path = Path(path)
        if not path.exists():
            return None
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None

    @classmethod
    def load_or_new(cls, path: str | Path) -> JobCheckpoint:
        return cls.load(path) or cls()

    def hydrate_from_artifacts(
        self,
        extracted_dir: str | Path,
        jsonl_path: str | Path,
        mineru_pages_dir: str | Path | None = None,
    ) -> None:
        """Fill gaps from page JSON and documents.jsonl after a crash that skipped checkpoint writes."""
        extracted_dir = Path(extracted_dir)
        if extracted_dir.exists():
            for file in extracted_dir.glob("page_*.json"):
                try:
                    page_no = int(file.stem.split("_")[1])
                except (IndexError, ValueError):
                    continue
                self.mark_extracted(page_no)

        if mineru_pages_dir:
            pages_root = Path(mineru_pages_dir)
            if pages_root.exists():
                for folder in pages_root.glob("page_*"):
                    if not folder.is_dir():
                        continue
                    try:
                        page_no = int(folder.name.split("_")[1])
                    except (IndexError, ValueError):
                        continue
                    self.mark_mineru(page_no)

        jsonl_path = Path(jsonl_path)
        if not jsonl_path.exists():
            return
        records = 0
        visuals = 0
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            records += 1
            if doc.get("asset_id"):
                visuals += 1
            page_no = doc.get("pdf_page_number")
            if page_no is not None:
                self.mark_extracted(int(page_no))
            if not self.book_id:
                self.book_id = doc.get("book_id")
        self.extracted_records = max(self.extracted_records, records)
        self.visual_assets = max(self.visual_assets, visuals)


def checkpoint_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / CHECKPOINT_FILENAME

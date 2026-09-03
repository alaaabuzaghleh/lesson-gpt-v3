from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import fitz  # PyMuPDF
from PIL import Image

from .ocr_cleanup import choose_page_text

if TYPE_CHECKING:
    from .mineru_parser import MinerUDocument


@dataclass
class PageData:
    pdf_page_number: int
    text_layer: str
    image_path: Path
    width: int
    height: int
    text_source: str = "pdf"
    mineru_blocks: list[dict] = field(default_factory=list)

    def as_data_url(self) -> str:
        data = self.image_path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{b64}"


class PDFReader:
    def __init__(self, pdf_path: str | Path, work_dir: str | Path, dpi: int = 180):
        self.pdf_path = Path(pdf_path).resolve()
        self.work_dir = Path(work_dir)
        self.pages_dir = self.work_dir / "pages"
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = dpi
        self.doc = fitz.open(self.pdf_path)
        self.mineru: MinerUDocument | None = None

    def attach_mineru(self, document: MinerUDocument | None) -> None:
        if document is None:
            return
        if self.mineru is None:
            self.mineru = document
            return
        self.mineru.merge(document)

    @property
    def page_count(self) -> int:
        return self.doc.page_count

    def close(self):
        self.doc.close()

    def render_page(self, page_number: int) -> PageData:
        page = self.doc[page_number - 1]
        pdf_text = page.get_text("text", sort=True) or ""
        mineru_page = self.mineru.page(page_number) if self.mineru is not None else None
        mineru_text = mineru_page.text if mineru_page is not None else ""
        text, text_source = choose_page_text(mineru_text, pdf_text)
        mineru_blocks = [block.as_prompt_dict() for block in mineru_page.blocks] if mineru_page else []
        image_path = self.pages_dir / f"page_{page_number:04d}.png"
        if not image_path.exists():
            scale = self.dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            pix.save(str(image_path))
        with Image.open(image_path) as img:
            width, height = img.size
        return PageData(page_number, text, image_path, width, height, text_source, mineru_blocks)

    def iter_pages(self, start: int = 1, end: int | None = None) -> Iterator[PageData]:
        end = end or self.page_count
        for n in range(start, min(end, self.page_count) + 1):
            yield self.render_page(n)

    def crop_bbox(self, page: PageData, bbox: dict, output_path: Path, padding_px: int = 8) -> Path:
        with Image.open(page.image_path) as img:
            x1 = max(0, int(img.width * bbox["x1"] / 1000) - padding_px)
            y1 = max(0, int(img.height * bbox["y1"] / 1000) - padding_px)
            x2 = min(img.width, int(img.width * bbox["x2"] / 1000) + padding_px)
            y2 = min(img.height, int(img.height * bbox["y2"] / 1000) + padding_px)
            if x2 <= x1 or y2 <= y1:
                raise ValueError("Invalid crop bbox")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.crop((x1, y1, x2, y2)).save(output_path)
        return output_path

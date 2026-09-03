from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass(frozen=True)
class RenderedPage:
    pdf_page_number: int
    image_path: Path
    width: int
    height: int


class PDFRenderer:
    def __init__(self, pdf_path: str | Path, pages_dir: str | Path, dpi: int = 180):
        self.pdf_path = Path(pdf_path).resolve()
        if not self.pdf_path.is_file():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        self.pages_dir = Path(pages_dir)
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = dpi
        self._doc = fitz.open(self.pdf_path)

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    def close(self) -> None:
        self._doc.close()

    def __enter__(self) -> PDFRenderer:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def render_page(self, page_number: int) -> RenderedPage:
        if page_number < 1 or page_number > self.page_count:
            raise ValueError(f"Page {page_number} out of range 1..{self.page_count}")
        page = self._doc[page_number - 1]
        zoom = self.dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image_path = self.pages_dir / f"page_{page_number:04d}.png"
        pix.save(image_path)
        return RenderedPage(
            pdf_page_number=page_number,
            image_path=image_path,
            width=pix.width,
            height=pix.height,
        )

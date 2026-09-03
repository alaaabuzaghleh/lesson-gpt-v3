from __future__ import annotations


def choose_page_text(mineru_text: str, pdf_text: str) -> tuple[str, str]:
    """Use MinerU output as-is whenever it produced any text."""
    if (mineru_text or "").strip():
        return mineru_text, "mineru"
    return pdf_text or "", "pdf"

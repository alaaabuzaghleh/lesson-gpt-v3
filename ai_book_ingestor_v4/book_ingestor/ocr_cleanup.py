from __future__ import annotations

import re

_FFFD = "\ufffd"
_PUA = re.compile(r"[\uE000-\uF8FF]")
_ISOLATED_DIACRITIC = re.compile(r"[\u064B-\u065F\u0670]")
_ARABIC_WORD_CHARS = r"\u0600-\u06FF"
_NOT_ARABIC = rf"(?<![{_ARABIC_WORD_CHARS}])"
_NOT_ARABIC_AFTER = rf"(?![{_ARABIC_WORD_CHARS}])"

# Isolated two-letter visual-order particles.
_TWO_LETTER_FIXES = (
    (re.compile(rf"{_NOT_ARABIC}يف{_NOT_ARABIC_AFTER}"), "في"),
    (re.compile(rf"{_NOT_ARABIC}نم{_NOT_ARABIC_AFTER}"), "من"),
    (re.compile(rf"{_NOT_ARABIC}نع{_NOT_ARABIC_AFTER}"), "عن"),
    (re.compile(rf"{_NOT_ARABIC}مبا{_NOT_ARABIC_AFTER}"), "بما"),
    (re.compile(rf"{_NOT_ARABIC}الغراض{_NOT_ARABIC_AFTER}"), "لاغراض"),
)
_ARTICLE_MEEM = re.compile(rf"{_NOT_ARABIC}امل")
_DOUBLE_ALEF_LAM = re.compile(r"اال")
_GLUED_PARTICLE = re.compile(
    rf"([{_ARABIC_WORD_CHARS}]{{3,}})(في|من|على)(?=$|[^{_ARABIC_WORD_CHARS}])"
)
_TRAILING_ALEF_PAREN = re.compile(r"\(\s*\)ا")
_LEADING_ADET = re.compile(r"(^|[(\u201c\u00ab])عدت(?=\s)")


def repair_arabic_ocr(text: str) -> str:
    """Fix common MinerU/PaddleOCR Arabic letter swaps without rewriting layout."""
    if not text:
        return ""
    text = text.replace(_FFFD, "")
    text = _PUA.sub("", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = _ISOLATED_DIACRITIC.sub("", text)
    text = _ARTICLE_MEEM.sub("الم", text)
    text = _DOUBLE_ALEF_LAM.sub("الا", text)
    for pattern, replacement in _TWO_LETTER_FIXES:
        text = pattern.sub(replacement, text)
    text = _GLUED_PARTICLE.sub(r"\1 \2", text)
    had_displaced_alef = bool(_TRAILING_ALEF_PAREN.search(text))
    text = _TRAILING_ALEF_PAREN.sub("", text)
    text = _LEADING_ADET.sub(r"\1أعدت", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if had_displaced_alef and re.match(r"أعدت\b", text):
        text = "(" + text
        if not text.endswith(")"):
            text += ")"
    return text


def choose_page_text(mineru_text: str, pdf_text: str) -> tuple[str, str]:
    """Prefer MinerU text, then apply Arabic OCR repairs."""
    if (mineru_text or "").strip():
        return repair_arabic_ocr(mineru_text), "mineru"
    return repair_arabic_ocr(pdf_text or ""), "pdf"

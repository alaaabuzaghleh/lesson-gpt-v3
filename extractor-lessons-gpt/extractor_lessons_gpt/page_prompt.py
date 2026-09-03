from __future__ import annotations


def build_page_prompt(*, page_number: int, language_hint: str) -> str:
    return (
        f"Extract all readable content from the attached textbook page image.\n"
        f"PDF page number: {page_number}\n"
        f"Language hint: {language_hint}\n\n"
        "Rules:\n"
        "- Preserve Arabic in correct logical reading order (not reversed visual order).\n"
        "- Transcribe headings, body text, captions, footnotes, and side notes faithfully.\n"
        "- Put math in LaTeX when possible; otherwise plain text.\n"
        "- Reconstruct tables as markdown in tables_markdown.\n"
        "- Use headings only for real titles (unit/chapter/lesson/section), not mid-sentence words.\n"
        "- If something is illegible, mention it in notes instead of guessing.\n"
        "- Return JSON matching the provided schema exactly."
    )


def build_system_prompt(schema_text: str) -> str:
    return (
        "You are a precise textbook OCR and structure extraction engine.\n"
        "Return ONLY one JSON object. No markdown fences, no commentary.\n"
        "The JSON must match this schema exactly:\n"
        f"{schema_text}"
    )

from __future__ import annotations

from .schemas import ExtractedBlock, QUESTION_TYPES, VISUAL_TYPES, VisualAnalysis


def block_quality_score(block: ExtractedBlock, visual: VisualAnalysis | None = None) -> float:
    score = block.confidence * 0.50

    if block.verbatim_text.strip():
        score += 0.12
    if block.bbox is not None:
        score += 0.08
    if block.title:
        score += 0.04
    if block.concepts or block.keywords:
        score += 0.04

    if block.content_type in QUESTION_TYPES:
        if block.question and (block.question.stem or block.verbatim_text):
            score += 0.10
        if block.question and block.question.number:
            score += 0.04
    elif block.content_type in VISUAL_TYPES:
        if block.caption or block.figure_label or block.concise_description:
            score += 0.04
        if visual is not None:
            score += visual.overall_confidence * 0.10
            if visual.verification.status == "passed":
                score += 0.08
            elif visual.verification.status in {"failed", "needs_retry"}:
                score -= 0.18
            elif visual.verification.status == "uncertain":
                score -= 0.05
    else:
        score += 0.08

    # Never reward an answer that was not explicitly visible.
    if block.question and block.question.visible_answer and not block.question.answer_is_explicitly_visible:
        score -= 0.40

    return max(0.0, min(1.0, round(score, 4)))


def ocr_page_is_sparse(text: str | None, indexable_blocks: int, min_chars: int = 20) -> bool:
    chars = len((text or "").strip())
    return chars < min_chars and indexable_blocks <= 0


def ocr_page_quality_score(text: str | None, indexable_blocks: int, source: str, min_chars: int = 20) -> float:
    chars = len((text or "").strip())
    if chars == 0 and indexable_blocks <= 0:
        return 0.15
    if chars < min_chars and indexable_blocks <= 0:
        return 0.35
    base = 0.9 if source == "mineru" else 0.45
    if indexable_blocks > 0:
        base = min(1.0, base + 0.05)
    return round(base, 4)


def ocr_completeness(
    *,
    start_page: int,
    end_page: int,
    ocr_pages: set[int],
    empty_pages: list[int],
    sparse_pages: list[int],
    failed_pages: list[int],
    empty_ratio_limit: float = 0.15,
) -> dict[str, object]:
    requested = max(1, end_page - start_page + 1)
    expected = set(range(start_page, end_page + 1))
    missing = sorted(expected - ocr_pages)
    coverage = round(len(ocr_pages & expected) / requested, 4)
    empty_ratio = round(len(empty_pages) / requested, 4)
    complete = coverage == 1.0 and not missing and not failed_pages
    recommended = complete and empty_ratio <= empty_ratio_limit
    return {
        "requested_pages": requested,
        "ocr_pages_present": len(ocr_pages & expected),
        "ocr_coverage": coverage,
        "missing_ocr_pages": missing,
        "empty_ocr_pages": empty_pages,
        "sparse_ocr_pages": sparse_pages,
        "failed_ocr_pages": failed_pages,
        "empty_ocr_ratio": empty_ratio,
        "ocr_complete": complete,
        "recommended_for_live_index": recommended,
    }

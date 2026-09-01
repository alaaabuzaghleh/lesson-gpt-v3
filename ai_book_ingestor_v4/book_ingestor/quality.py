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

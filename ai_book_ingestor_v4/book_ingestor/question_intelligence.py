from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .normalizer import normalize_general
from .schemas import ContentType, ExtractedBlock, PageExtraction, QuestionData, QuestionReference, QUESTION_TYPES


LEGACY_FORMAT_BY_TYPE = {
    ContentType.MULTIPLE_CHOICE: "multiple_choice",
    ContentType.TRUE_FALSE: "true_false",
    ContentType.FILL_BLANK: "fill_blank",
    ContentType.ESSAY_QUESTION: "essay",
    ContentType.PROBLEM: "problem",
    ContentType.THINKING_QUESTION: "open_ended",
    ContentType.REVIEW_QUESTION: "open_ended",
    ContentType.LESSON_QUESTION: "open_ended",
    ContentType.UNIT_QUESTION: "open_ended",
    ContentType.EXERCISE: "exercise",
}

LEGACY_SCOPE_BY_TYPE = {
    ContentType.LESSON_QUESTION: "lesson_end",
    ContentType.UNIT_QUESTION: "unit_end",
    ContentType.THINKING_QUESTION: "inside_lesson",
    ContentType.REVIEW_QUESTION: "review",
}

# Heading/group recognition. Patterns intentionally cover Arabic/English and remain conservative.
SCOPE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("previous_exam", ("امتحان سابق", "اسئلة سنوات سابقة", "أسئلة سنوات سابقة", "past exam", "previous exam", "past paper")),
    ("practice_test", ("اختبار تجريبي", "نموذج اختبار", "practice test", "mock test", "sample test")),
    ("exam", ("اختبار", "امتحان", "test", "exam", "assessment")),
    ("final_review", ("المراجعة النهائية", "مراجعة نهائية", "final review", "cumulative review")),
    ("semester_review", ("مراجعة الفصل الدراسي", "مراجعة نهاية الفصل الدراسي", "semester review", "term review")),
    ("book_review", ("مراجعة الكتاب", "مراجعة شاملة", "book review", "comprehensive review")),
    ("unit_end", ("اسئلة الوحدة", "أسئلة الوحدة", "مراجعة الوحدة", "اختبر نفسك الوحدة", "unit questions", "unit review", "review the unit")),
    ("chapter_end", ("اسئلة الفصل", "أسئلة الفصل", "مراجعة الفصل", "chapter questions", "chapter review", "review the chapter")),
    ("lesson_end", ("اسئلة الدرس", "أسئلة الدرس", "مراجعة الدرس", "تقويم الدرس", "lesson questions", "lesson review", "review the lesson")),
    ("section_end", ("اسئلة القسم", "أسئلة القسم", "مراجعة القسم", "section questions", "section review")),
    ("checkpoint", ("تحقق من فهمك", "اتحقق من فهمي", "أتحقق من فهمي", "اختبر فهمك", "اختبر نفسي", "check your understanding", "check your learning", "quick check", "self check")),
    ("worked_example_followup", ("جرب بنفسك", "حاول بنفسك", "try it yourself", "your turn", "now try")),
    ("activity_question", ("اسئلة النشاط", "أسئلة النشاط", "activity questions", "activity question")),
    ("experiment_question", ("اسئلة التجربة", "أسئلة التجربة", "experiment questions", "lab questions")),
    ("reading_passage_question", ("اسئلة النص", "أسئلة النص", "اسئلة القراءة", "أسئلة القراءة", "reading questions", "passage questions", "comprehension questions")),
]

FORMAT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("true_false", ("صح ام خطا", "صح أو خطأ", "صواب ام خطا", "صواب أو خطأ", "true or false", "true/false")),
    ("fill_blank", ("املا الفراغ", "املأ الفراغ", "اكمل الفراغ", "أكمل الفراغ", "fill in the blank", "fill the blank", "complete the sentence")),
    ("matching", ("صل بين", "طابق", "وفق بين", "match the", "matching")),
    ("ordering", ("رتب", "رتب ما يلي", "ضع بالترتيب", "order the", "arrange the", "sequence the")),
    ("classification", ("صنف", "صنّف", "classify", "categorize", "group the")),
    ("comparison", ("قارن", "compare", "contrast")),
    ("justify", ("علل", "برر", "فسر السبب", "justify", "give a reason", "explain why")),
    ("explain", ("فسر", "اشرح", "وضّح", "وضح", "explain", "describe how")),
    ("prove", ("اثبت", "أثبت", "برهن", "prove", "show that")),
    ("derive", ("اشتق", "استنتج العلاقة", "derive")),
    ("calculate", ("احسب", "اوجد قيمة", "أوجد قيمة", "جد قيمة", "calculate", "compute", "find the value", "solve for")),
    ("label_diagram", ("سم الاجزاء", "سم الأجزاء", "اكتب اسماء الاجزاء", "اكتب أسماء الأجزاء", "label the diagram", "label the figure", "name the parts")),
    ("interpret_graph", ("الرسم البياني", "المنحنى", "graph", "chart")),
    ("interpret_table", ("الجدول", "table")),
    ("interpret_map", ("الخريطة", "map")),
    ("image_question", ("الصورة", "الشكل", "figure", "image", "picture", "diagram")),
    ("definition", ("عرف", "عرّف", "ما المقصود", "ما تعريف", "define", "what is meant by", "what is the definition")),
]

PURPOSE_PATTERNS: list[tuple[str, str, tuple[str, ...]]] = [
    ("creation", "create", ("صمم", "انشئ", "أنشئ", "اقترح", "ابتكر", "create", "design", "develop", "propose", "construct")),
    ("evaluation", "evaluate", ("قيم", "قيّم", "انقد", "برر رايك", "برر رأيك", "evaluate", "judge", "critique", "defend")),
    ("critical_thinking", "analyze", ("حلل", "استنتج", "قارن", "ماذا يحدث لو", "توقع", "analyze", "infer", "compare", "what would happen if", "predict")),
    ("application", "apply", ("طبق", "استخدم", "احسب", "حل", "apply", "use", "calculate", "solve")),
    ("understanding", "understand", ("فسر", "اشرح", "وضح", "علل", "explain", "describe", "summarize", "why")),
    ("recall", "remember", ("اذكر", "عدد", "عرف", "عرّف", "ما هو", "list", "name", "define", "state", "identify")),
]

REFERENCE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("graph", ("الرسم البياني", "المنحنى", "graph", "chart")),
    ("table", ("الجدول", "table")),
    ("map", ("الخريطة", "map")),
    ("figure", ("الشكل", "الرسم", "figure", "diagram", "illustration")),
    ("passage", ("النص", "الفقرة", "القصيدة", "passage", "text", "poem", "reading")),
    ("equation", ("المعادلة", "العلاقة", "القانون", "equation", "formula")),
]


def _norm(value: str | None) -> str:
    return normalize_general(value or "")


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    t = _norm(text)
    return any(_norm(p) in t for p in phrases)


def _short_heading_text(block: ExtractedBlock) -> str:
    candidates = [block.title or "", block.verbatim_text or "", block.concise_description or ""]
    text = " ".join(x.strip() for x in candidates if x and x.strip())
    return text[:500]


def _scope_from_text(text: str) -> str | None:
    for scope, patterns in SCOPE_PATTERNS:
        if _contains_any(text, patterns):
            return scope
    return None


def _format_from_text(text: str, question: QuestionData, content_type: ContentType) -> str:
    if question.format:
        return question.format
    if content_type in LEGACY_FORMAT_BY_TYPE and LEGACY_FORMAT_BY_TYPE[content_type] not in {"open_ended", "exercise"}:
        return LEGACY_FORMAT_BY_TYPE[content_type]
    if question.choices:
        return "multiple_choice"
    for fmt, patterns in FORMAT_PATTERNS:
        if _contains_any(text, patterns):
            return fmt
    if content_type == ContentType.PROBLEM:
        return "problem"
    if content_type == ContentType.EXERCISE:
        return "exercise"
    return "open_ended"


def _purpose_and_bloom(text: str, question: QuestionData, content_type: ContentType) -> tuple[str, str]:
    if question.purpose and question.bloom_level:
        return question.purpose, question.bloom_level
    for purpose, bloom, patterns in PURPOSE_PATTERNS:
        if _contains_any(text, patterns):
            return question.purpose or purpose, question.bloom_level or bloom
    if content_type == ContentType.THINKING_QUESTION:
        return question.purpose or "critical_thinking", question.bloom_level or "analyze"
    return question.purpose or "assessment", question.bloom_level or "unknown"


def _extract_reference_label(text: str, reference_type: str) -> str | None:
    # Arabic/English figure/table/graph/map numbers, e.g. الشكل 3-2 / Figure 4.1.
    patterns = {
        "figure": r"(?:الشكل|الرسم|figure|diagram)\s*[:#\-]?\s*([0-9٠-٩]+(?:[.\-][0-9٠-٩]+)?)",
        "graph": r"(?:الرسم البياني|المنحنى|graph|chart)\s*[:#\-]?\s*([0-9٠-٩]+(?:[.\-][0-9٠-٩]+)?)",
        "table": r"(?:الجدول|table)\s*[:#\-]?\s*([0-9٠-٩]+(?:[.\-][0-9٠-٩]+)?)",
        "map": r"(?:الخريطة|map)\s*[:#\-]?\s*([0-9٠-٩]+(?:[.\-][0-9٠-٩]+)?)",
    }
    pat = patterns.get(reference_type)
    if not pat:
        return None
    m = re.search(pat, text, flags=re.IGNORECASE)
    return m.group(1) if m else None


def _infer_references(question: QuestionData, text: str) -> None:
    existing = {(r.reference_type, r.reference_text or "", r.figure_label or "") for r in question.references}
    for ref_type, patterns in REFERENCE_PATTERNS:
        if _contains_any(text, patterns):
            label = _extract_reference_label(text, ref_type)
            key = (ref_type, text[:250], label or "")
            if key not in existing:
                question.references.append(
                    QuestionReference(
                        reference_type=ref_type,
                        reference_text=text[:250] or None,
                        figure_label=label,
                        confidence=0.78,
                    )
                )
    types = {r.reference_type for r in question.references}
    question.requires_graph = question.requires_graph or "graph" in types
    question.requires_table = question.requires_table or "table" in types
    question.requires_map = question.requires_map or "map" in types
    question.requires_passage = question.requires_passage or "passage" in types
    question.requires_equation = question.requires_equation or "equation" in types
    question.requires_visual = question.requires_visual or bool(types & {"figure", "graph", "table", "map", "visual_asset"})


def _is_question_block(block: ExtractedBlock) -> bool:
    return block.question is not None or block.content_type in QUESTION_TYPES


def _question_group_from_preceding(page: PageExtraction, idx: int) -> str | None:
    # Search a few immediately preceding blocks for a short review/checkpoint heading.
    for j in range(idx - 1, max(-1, idx - 5), -1):
        b = page.blocks[j]
        text = _short_heading_text(b)
        if not text:
            continue
        scope = _scope_from_text(text)
        if scope:
            return (b.title or b.verbatim_text or b.concise_description or "").strip()[:300]
        # Stop at substantial prose instead of pulling a remote heading.
        if len((b.verbatim_text or "").strip()) > 350 and b.content_type not in {ContentType.SECTION_HEADING, ContentType.LESSON_TITLE, ContentType.CHAPTER_TITLE, ContentType.UNIT_TITLE}:
            break
    return None


def _structural_end_scope(pages: list[PageExtraction], page_index: int, block_index: int) -> str | None:
    page = pages[page_index]
    # Structural inference is used only for a cluster near the end of a page/lesson.
    question_blocks_after = sum(1 for b in page.blocks[block_index:] if _is_question_block(b))
    non_question_after = sum(1 for b in page.blocks[block_index + 1:] if not _is_question_block(b) and (b.verbatim_text or b.title))
    if question_blocks_after == 0 or non_question_after > 2:
        return None

    for next_page in pages[page_index + 1: page_index + 3]:
        if next_page.explicit_unit_title:
            return "unit_end"
        if next_page.explicit_chapter_title:
            return "chapter_end"
        if next_page.explicit_lesson_title:
            return "lesson_end"
    return None


def _classify_one_question(
    block: ExtractedBlock,
    page: PageExtraction,
    page_index: int,
    block_index: int,
    pages: list[PageExtraction],
) -> None:
    if block.question is None:
        block.question = QuestionData(stem=block.verbatim_text or None)
    q = block.question
    if not q.stem and block.verbatim_text:
        q.stem = block.verbatim_text

    evidence: list[str] = list(q.classification_evidence)
    group = q.group_title or _question_group_from_preceding(page, block_index)
    if group:
        q.group_title = group
        evidence.append(f"group_heading:{group[:100]}")

    combined = "\n".join(x for x in [group or "", block.title or "", q.instructions or "", q.stem or "", block.verbatim_text or ""] if x)

    if not q.scope:
        q.scope = _scope_from_text(combined)
        if q.scope:
            evidence.append(f"scope_from_visible_text:{q.scope}")
    if not q.scope and block.content_type in LEGACY_SCOPE_BY_TYPE:
        q.scope = LEGACY_SCOPE_BY_TYPE[block.content_type]
        evidence.append(f"scope_from_legacy_type:{block.content_type.value}")
    if not q.scope:
        structural_scope = _structural_end_scope(pages, page_index, block_index)
        if structural_scope:
            q.scope = structural_scope
            evidence.append(f"scope_from_neighboring_hierarchy:{structural_scope}")
    if not q.scope:
        q.scope = "inside_lesson"
        evidence.append("scope_default:inside_lesson")

    q.format = _format_from_text(combined, q, block.content_type)
    purpose, bloom = _purpose_and_bloom(combined, q, block.content_type)
    q.purpose = purpose
    q.bloom_level = bloom
    q.difficulty = q.difficulty or block.difficulty

    _infer_references(q, combined)

    # Legacy types are normalized to a single queryable content type. Original
    # semantics remain in question fields and block.subtype.
    if block.content_type != ContentType.QUESTION:
        if not block.subtype:
            block.subtype = block.content_type.value
        block.content_type = ContentType.QUESTION

    block.bloom_level = q.bloom_level if q.bloom_level not in {None, "unknown"} else block.bloom_level
    block.difficulty = q.difficulty or block.difficulty

    # Confidence is higher when visible group/type evidence exists; structural/default
    # inference remains intentionally lower.
    if any(x.startswith("scope_from_visible_text") or x.startswith("group_heading") for x in evidence):
        conf = max(q.classification_confidence, 0.92)
    elif any(x.startswith("scope_from_legacy_type") for x in evidence):
        conf = max(q.classification_confidence, 0.88)
    elif any(x.startswith("scope_from_neighboring_hierarchy") for x in evidence):
        conf = max(q.classification_confidence, 0.80)
    else:
        conf = max(q.classification_confidence, 0.68)
    q.classification_confidence = min(1.0, conf)
    q.classification_evidence = list(dict.fromkeys(evidence))

    # Recurse into subquestions: they inherit group/scope but retain independent
    # format/purpose/Bloom and dependencies.
    for child in q.children:
        child.group_title = child.group_title or q.group_title
        child.scope = child.scope or q.scope
        child.difficulty = child.difficulty or q.difficulty
        child_text = "\n".join(x for x in [child.instructions or "", child.stem or ""] if x)
        child.format = _format_from_text(child_text, child, ContentType.QUESTION)
        cp, cb = _purpose_and_bloom(child_text, child, ContentType.QUESTION)
        child.purpose = child.purpose or cp
        child.bloom_level = child.bloom_level or cb
        _infer_references(child, child_text)
        child.classification_confidence = max(child.classification_confidence, q.classification_confidence * 0.95)
        child.classification_evidence = list(dict.fromkeys(child.classification_evidence + ["inherited_parent_context"]))


class QuestionIntelligenceEngine:
    """Post-process page extraction into a consistent question ontology.

    This layer is deliberately independent of subject and language. It uses visible
    Arabic/English cues plus page/hierarchy structure, and keeps unknown values open-ended.
    """

    def enrich_pages(self, pages: list[PageExtraction]) -> list[PageExtraction]:
        ordered = sorted(pages, key=lambda p: p.pdf_page_number)
        for pi, page in enumerate(ordered):
            for bi, block in enumerate(page.blocks):
                if _is_question_block(block):
                    _classify_one_question(block, page, pi, bi, ordered)
        return ordered

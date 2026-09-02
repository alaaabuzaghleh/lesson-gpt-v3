from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ContentType(str, Enum):
    COVER = "cover"
    COPYRIGHT = "copyright"
    TOC = "table_of_contents"
    TOC_ENTRY = "toc_entry"
    PREFACE = "preface"
    INTRODUCTION = "introduction"
    CHAPTER_TITLE = "chapter_title"
    UNIT_TITLE = "unit_title"
    LESSON_TITLE = "lesson_title"
    SECTION_HEADING = "section_heading"
    LEARNING_OBJECTIVE = "learning_objective"
    KEY_TERM = "key_term"
    DEFINITION = "definition"
    THEORY = "theory"
    THEOREM = "theorem"
    LAW = "law"
    PRINCIPLE = "principle"
    RULE = "rule"
    FORMULA = "formula"
    EQUATION = "equation"
    DERIVATION = "derivation"
    PROOF = "proof"
    EXPLANATION = "explanation"
    CONCEPT = "concept"
    FACT = "fact"
    NOTE = "note"
    WARNING = "warning"
    TIP = "tip"
    SUMMARY = "summary"
    EXAMPLE = "example"
    WORKED_EXAMPLE = "worked_example"
    EXERCISE = "exercise"
    QUESTION = "question"
    LESSON_QUESTION = "lesson_question"
    UNIT_QUESTION = "unit_question"
    THINKING_QUESTION = "thinking_question"
    REVIEW_QUESTION = "review_question"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    ESSAY_QUESTION = "essay_question"
    PROBLEM = "problem"
    ACTIVITY = "activity"
    EXPERIMENT = "experiment"
    LAB = "lab"
    PROCEDURE = "procedure"
    OBSERVATION = "observation"
    ANALYSIS = "analysis"
    DISCUSSION = "discussion"
    CASE_STUDY = "case_study"
    READING_PASSAGE = "reading_passage"
    VOCABULARY = "vocabulary"
    GRAMMAR_RULE = "grammar_rule"
    POEM = "poem"
    STORY = "story"
    SOURCE_TEXT = "source_text"
    HISTORICAL_EVENT = "historical_event"
    TIMELINE = "timeline"
    MAP = "map"
    FIGURE = "figure"
    DIAGRAM = "diagram"
    GRAPH = "graph"
    CHART = "chart"
    TABLE = "table"
    IMAGE = "image"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    REFERENCE = "reference"
    ANSWER = "answer"
    ANSWER_KEY = "answer_key"
    RUBRIC = "rubric"
    GLOSSARY = "glossary"
    INDEX = "index"
    OTHER = "other"


CONTENT_TYPE_ALIASES = {
    "title": "section_heading",
    "heading": "section_heading",
    "header": "section_heading",
    "headline": "section_heading",
    "subheading": "section_heading",
    "subtitle": "section_heading",
    "page_title": "lesson_title",
    "lesson": "lesson_title",
    "chapter": "chapter_title",
    "unit": "unit_title",
    "paragraph": "explanation",
    "text": "explanation",
    "body": "explanation",
    "body_text": "explanation",
    "content": "explanation",
    "callout": "note",
    "sidebar": "note",
    "box": "note",
    "highlight": "note",
    "quote": "source_text",
    "photo": "image",
    "picture": "image",
    "illustration": "figure",
    "drawing": "figure",
    "math": "formula",
    "objective": "learning_objective",
    "objectives": "learning_objective",
    "term": "key_term",
    "toc": "table_of_contents",
    "contents": "table_of_contents",
    "quiz": "question",
    "homework": "exercise",
    "solution": "answer",
    "solutions": "answer_key",
    "list": "explanation",
    "bullet": "explanation",
    "bullets": "explanation",
}


def coerce_content_type(value: Any) -> ContentType:
    if isinstance(value, ContentType):
        return value
    if value is None or str(value).strip() == "":
        return ContentType.OTHER
    raw = str(value).strip().casefold().replace("-", "_").replace(" ", "_")
    for item in ContentType:
        if raw == item.value or raw == item.name.casefold():
            return item
    alias = CONTENT_TYPE_ALIASES.get(raw)
    if alias:
        return ContentType(alias)
    for item in ContentType:
        if raw.endswith("_" + item.value) or item.value in raw:
            return item
    return ContentType.OTHER


VISUAL_TYPES = {
    ContentType.MAP,
    ContentType.FIGURE,
    ContentType.DIAGRAM,
    ContentType.GRAPH,
    ContentType.CHART,
    ContentType.TABLE,
    ContentType.IMAGE,
    ContentType.TIMELINE,
}

QUESTION_TYPES = {
    ContentType.QUESTION,
    ContentType.EXERCISE,
    ContentType.LESSON_QUESTION,
    ContentType.UNIT_QUESTION,
    ContentType.THINKING_QUESTION,
    ContentType.REVIEW_QUESTION,
    ContentType.MULTIPLE_CHOICE,
    ContentType.TRUE_FALSE,
    ContentType.FILL_BLANK,
    ContentType.ESSAY_QUESTION,
    ContentType.PROBLEM,
}


class BBox(BaseModel):
    """Normalized coordinates from 0..1000 relative to the containing image."""

    x1: int = Field(ge=0, le=1000)
    y1: int = Field(ge=0, le=1000)
    x2: int = Field(ge=0, le=1000)
    y2: int = Field(ge=0, le=1000)

    @field_validator("x2")
    @classmethod
    def validate_x2(cls, v: int, info):
        if v <= info.data.get("x1", 0):
            raise ValueError("x2 must be greater than x1")
        return v

    @field_validator("y2")
    @classmethod
    def validate_y2(cls, v: int, info):
        if v <= info.data.get("y1", 0):
            raise ValueError("y2 must be greater than y1")
        return v


class QuestionReference(BaseModel):
    """A dependency or source explicitly referenced by a question."""

    reference_type: str  # visual_asset | figure | graph | table | map | passage | equation | example | other
    reference_text: Optional[str] = None
    target_id: Optional[str] = None
    figure_label: Optional[str] = None
    page_number: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0, le=1)


class QuestionData(BaseModel):
    """General bilingual representation of any textbook question.

    Scope (where the question appears) is deliberately separate from format
    (how the student must answer) and purpose/Bloom level (why it is asked).
    """

    question_id: Optional[str] = None
    parent_question_id: Optional[str] = None
    number: Optional[str] = None
    sub_number: Optional[str] = None
    group_title: Optional[str] = None

    # Location in the pedagogical structure. Open-ended strings keep the schema
    # usable for unfamiliar curricula while the intelligence engine normalizes
    # common values such as checkpoint, lesson_end, chapter_end and unit_end.
    scope: Optional[str] = None

    # Answer form: multiple_choice, true_false, calculate, explain,
    # label_diagram, interpret_graph, reading_comprehension, etc.
    format: Optional[str] = None

    # Educational intent: recall, understanding, application, problem_solving,
    # critical_thinking, analysis, evaluation, creation, assessment, etc.
    purpose: Optional[str] = None
    bloom_level: Optional[str] = None
    difficulty: Optional[str] = None

    stem: Optional[str] = None
    instructions: Optional[str] = None
    choices: list[str] = Field(default_factory=list)

    visible_answer: Optional[str] = None
    answer_is_explicitly_visible: bool = False

    requires_visual: bool = False
    requires_table: bool = False
    requires_graph: bool = False
    requires_map: bool = False
    requires_passage: bool = False
    requires_equation: bool = False

    references: list[QuestionReference] = Field(default_factory=list)
    children: list["QuestionData"] = Field(default_factory=list)

    classification_confidence: float = Field(default=0.0, ge=0, le=1)
    classification_evidence: list[str] = Field(default_factory=list)


class GraphData(BaseModel):
    title: Optional[str] = None
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    legend: list[str] = Field(default_factory=list)
    trends: list[str] = Field(default_factory=list)


class TableData(BaseModel):
    headers: list[str] = Field(default_factory=list)
    markdown: Optional[str] = None


class EvidenceRef(BaseModel):
    source: str
    detail: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0, le=1)


class VisualTextSpan(BaseModel):
    text: str
    bbox: Optional[BBox] = None
    language: Optional[str] = None
    role: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0, le=1)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class VisualEntity(BaseModel):
    id: str
    entity_type: str
    name: Optional[str] = None
    label: Optional[str] = None
    bbox: Optional[BBox] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.8, ge=0, le=1)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class VisualRelationship(BaseModel):
    source_id: str
    target_id: str
    relation: str
    direction: Optional[str] = None
    label: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0, le=1)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class VisualArrow(BaseModel):
    id: str
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    label: Optional[str] = None
    direction: Optional[str] = None
    bbox: Optional[BBox] = None
    confidence: float = Field(default=0.8, ge=0, le=1)


class VisualLegendItem(BaseModel):
    marker: Optional[str] = None
    meaning: Optional[str] = None
    bbox: Optional[BBox] = None
    confidence: float = Field(default=0.8, ge=0, le=1)


class VisualAxis(BaseModel):
    orientation: Optional[str] = None
    label: Optional[str] = None
    unit: Optional[str] = None
    minimum: Optional[str] = None
    maximum: Optional[str] = None
    tick_labels: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)


class VisualMeasurement(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    applies_to: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0, le=1)


class VisualStep(BaseModel):
    order: Optional[int] = None
    label: Optional[str] = None
    description: str
    entity_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)


class VisualColorMeaning(BaseModel):
    color_or_pattern: str
    meaning: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0, le=1)


class VisualVerification(BaseModel):
    status: str = "unverified"  # passed | uncertain | needs_retry | failed | unverified
    confidence: float = Field(default=0.0, ge=0, le=1)
    supported_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualAnalysis(BaseModel):
    """Open-ended representation for any educational visual in any subject."""

    visual_type: str = "unknown"
    visual_subtype: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    figure_label: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    summary: Optional[str] = None
    educational_role: Optional[str] = None

    visible_text: list[VisualTextSpan] = Field(default_factory=list)
    labels: list[VisualTextSpan] = Field(default_factory=list)
    entities: list[VisualEntity] = Field(default_factory=list)
    regions: list[VisualEntity] = Field(default_factory=list)
    arrows: list[VisualArrow] = Field(default_factory=list)
    relationships: list[VisualRelationship] = Field(default_factory=list)
    legend: list[VisualLegendItem] = Field(default_factory=list)
    axes: list[VisualAxis] = Field(default_factory=list)
    measurements: list[VisualMeasurement] = Field(default_factory=list)
    steps: list[VisualStep] = Field(default_factory=list)
    colors_with_meaning: list[VisualColorMeaning] = Field(default_factory=list)

    symbols: list[str] = Field(default_factory=list)
    equations: list[str] = Field(default_factory=list)
    data_points: list[dict[str, Any]] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    raw_attributes: dict[str, Any] = Field(default_factory=dict)

    confidence_by_field: dict[str, float] = Field(default_factory=dict)
    overall_confidence: float = Field(default=0.0, ge=0, le=1)
    verification: VisualVerification = Field(default_factory=VisualVerification)


class ExtractedBlock(BaseModel):
    sequence: int = Field(ge=1)
    content_type: ContentType = ContentType.OTHER
    subtype: Optional[str] = None
    title: Optional[str] = None
    verbatim_text: str = ""
    concise_description: Optional[str] = None
    bbox: Optional[BBox] = None
    language: Optional[str] = None

    concepts: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)

    difficulty: Optional[str] = None
    bloom_level: Optional[str] = None
    importance: Optional[str] = None

    question: Optional[QuestionData] = None
    graph: Optional[GraphData] = None
    table: Optional[TableData] = None

    figure_label: Optional[str] = None
    caption: Optional[str] = None
    cross_references: list[str] = Field(default_factory=list)

    confidence: float = Field(default=0.8, ge=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def _keep_unknown_content_type(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = data.get("content_type")
        if isinstance(raw, str) and raw.strip():
            allowed = {item.value for item in ContentType}
            if raw.strip().casefold().replace("-", "_").replace(" ", "_") not in allowed and not data.get("subtype"):
                data["subtype"] = raw.strip()
        return data

    @field_validator("content_type", mode="before")
    @classmethod
    def _coerce_content_type(cls, value: Any) -> ContentType:
        return coerce_content_type(value)


class PageExtraction(BaseModel):
    pdf_page_number: int = Field(ge=1)
    printed_page_number: Optional[str] = None
    printed_page_confidence: float = Field(default=0.0, ge=0, le=1)

    explicit_unit_title: Optional[str] = None
    explicit_chapter_title: Optional[str] = None
    explicit_lesson_title: Optional[str] = None
    explicit_section_title: Optional[str] = None

    page_language: Optional[str] = None
    page_kind: Optional[str] = None
    blocks: list[ExtractedBlock] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)


class BookMetadata(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    country: Optional[str] = None
    curriculum: Optional[str] = None
    education_system: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    semester: Optional[str] = None
    academic_year: Optional[str] = None
    edition: Optional[str] = None
    publisher: Optional[str] = None
    language: Optional[str] = None
    isbn: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence_pages: list[int] = Field(default_factory=list)


class HierarchyContext(BaseModel):
    unit_title: Optional[str] = None
    chapter_title: Optional[str] = None
    lesson_title: Optional[str] = None
    section_title: Optional[str] = None


class IndexDocument(BaseModel):
    id: str
    book_id: str
    book_title: Optional[str] = None

    country: Optional[str] = None
    curriculum: Optional[str] = None
    education_system: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    semester: Optional[str] = None
    academic_year: Optional[str] = None
    language: Optional[str] = None

    pdf_page_number: int
    printed_page_number: Optional[str] = None

    unit_title: Optional[str] = None
    chapter_title: Optional[str] = None
    lesson_title: Optional[str] = None
    section_title: Optional[str] = None
    hierarchy_path: list[str] = Field(default_factory=list)

    sequence: int
    content_type: str
    subtype: Optional[str] = None
    title: Optional[str] = None
    text: str = ""
    normalized_text: str = ""
    search_text: str = ""

    concepts: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)

    difficulty: Optional[str] = None
    bloom_level: Optional[str] = None
    importance: Optional[str] = None

    question: Optional[dict[str, Any]] = None
    question_id: Optional[str] = None
    question_parent_id: Optional[str] = None
    question_number: Optional[str] = None
    question_group: Optional[str] = None
    question_scope: Optional[str] = None
    question_format: Optional[str] = None
    question_purpose: Optional[str] = None
    question_bloom_level: Optional[str] = None
    question_difficulty: Optional[str] = None
    question_requires_visual: bool = False
    question_requires_table: bool = False
    question_requires_graph: bool = False
    question_requires_map: bool = False
    question_requires_passage: bool = False
    question_requires_equation: bool = False
    question_reference_ids: list[str] = Field(default_factory=list)
    question_reference_text: list[str] = Field(default_factory=list)

    graph: Optional[dict[str, Any]] = None
    table: Optional[dict[str, Any]] = None
    figure_label: Optional[str] = None
    caption: Optional[str] = None
    cross_references: list[str] = Field(default_factory=list)

    # Visual asset fields are searchable summaries plus the full raw analysis.
    asset_id: Optional[str] = None
    visual_type: Optional[str] = None
    visual_subtype: Optional[str] = None
    visual_summary: Optional[str] = None
    visual_text: str = ""
    visual_labels: list[str] = Field(default_factory=list)
    visual_concepts: list[str] = Field(default_factory=list)
    visual_verification_status: Optional[str] = None
    visual_analysis: Optional[dict[str, Any]] = None

    bbox: Optional[dict[str, int]] = None
    asset_path: Optional[str] = None
    page_image_path: Optional[str] = None
    source_pdf_path: Optional[str] = None

    confidence: float = 0.0
    quality_score: float = 0.0
    extraction_notes: list[str] = Field(default_factory=list)

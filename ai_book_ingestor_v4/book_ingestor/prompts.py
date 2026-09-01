from __future__ import annotations

import json
from .schemas import ContentType

CONTENT_TYPES = [x.value for x in ContentType]

BOOK_METADATA_SYSTEM = """You are a meticulous bilingual textbook cataloging system. Analyze only evidence visible on supplied pages. Support Arabic, English, and mixed Arabic/English books. Never guess missing metadata. Return strict JSON only."""

BOOK_METADATA_PROMPT = """
Analyze the supplied beginning pages of a school textbook and identify catalog metadata.
Return exactly:
{
  "title": null,
  "subtitle": null,
  "country": null,
  "curriculum": null,
  "education_system": null,
  "grade": null,
  "subject": null,
  "semester": null,
  "academic_year": null,
  "edition": null,
  "publisher": null,
  "language": null,
  "isbn": null,
  "confidence": 0.0,
  "evidence_pages": []
}
Rules:
- null means not explicitly supported.
- Never infer country merely from language.
- Preserve official Arabic or English names exactly where possible.
- language may be "ar", "en", "mixed", or another visible language code/name.
- evidence_pages contains PDF page numbers that support the metadata.
"""

PAGE_SYSTEM = """You are a high-precision educational document understanding engine for Arabic and English textbooks. Your task is PAGE SEGMENTATION AND VERBATIM EXTRACTION, not teaching and not deep visual interpretation. Extract only visible evidence. Never solve questions, invent labels, infer missing answers, translate source wording, or add external knowledge. Return strict JSON only."""


def page_prompt(pdf_page_number: int, text_layer: str, book_meta: dict) -> str:
    meta = json.dumps(book_meta, ensure_ascii=False)
    return f"""
PDF page number: {pdf_page_number}
Known/overridden book metadata: {meta}

PDF text layer (may be incomplete, reordered, or empty; page image is authoritative):
---BEGIN TEXT LAYER---
{text_layer[:22000]}
---END TEXT LAYER---

Extract every educationally meaningful visible block in natural reading order.
Allowed content_type values:
{json.dumps(CONTENT_TYPES, ensure_ascii=False)}
For every student-facing question/exercise/problem, prefer the unified content_type "question"; legacy question-like values exist only for backward compatibility.

Return exactly:
{{
  "pdf_page_number": {pdf_page_number},
  "printed_page_number": null,
  "printed_page_confidence": 0.0,
  "explicit_unit_title": null,
  "explicit_chapter_title": null,
  "explicit_lesson_title": null,
  "explicit_section_title": null,
  "page_language": null,
  "page_kind": null,
  "blocks": [
    {{
      "sequence": 1,
      "content_type": "explanation",
      "subtype": null,
      "title": null,
      "verbatim_text": "",
      "concise_description": null,
      "bbox": {{"x1":0,"y1":0,"x2":1000,"y2":1000}},
      "language": null,
      "concepts": [],
      "keywords": [],
      "aliases": [],
      "skills": [],
      "prerequisites": [],
      "difficulty": null,
      "bloom_level": null,
      "importance": null,
      "question": null,
      "graph": null,
      "table": null,
      "figure_label": null,
      "caption": null,
      "cross_references": [],
      "confidence": 0.0
    }}
  ],
  "extraction_notes": []
}}

Rules:
1. verbatim_text must preserve the visible source wording exactly. Never translate Arabic to English or English to Arabic.
2. A block is one meaningful retrievable unit: heading, definition, paragraph, theorem, law, formula, worked example, question, activity, source text, visual region, table, etc.
3. If a heading explicitly changes unit/chapter/lesson/section, set the corresponding explicit_* field. Otherwise null. Never inherit or guess a heading inside this extraction step.
4. printed_page_number is the page number visibly printed on the textbook page, not the PDF position.
5. bbox is normalized 0..1000 relative to the FULL PAGE and should be tight enough to crop the block later.
6. Questions: ALWAYS use content_type="question" and populate question with the richest visible structure possible. Keep WHERE the question appears separate from HOW it is answered. Use this shape:
   {{
     "number": null, "sub_number": null, "group_title": null,
     "scope": null,
     "format": null,
     "purpose": null, "bloom_level": null, "difficulty": null,
     "stem": null, "instructions": null, "choices": [],
     "visible_answer": null, "answer_is_explicitly_visible": false,
     "requires_visual": false, "requires_table": false, "requires_graph": false,
     "requires_map": false, "requires_passage": false, "requires_equation": false,
     "references": [], "children": [],
     "classification_confidence": 0.0, "classification_evidence": []
   }}
   - scope describes location/pedagogical group, e.g. inside_lesson, checkpoint, worked_example_followup, section_end, lesson_end, chapter_end, unit_end, book_review, semester_review, final_review, exam, practice_test, previous_exam, activity_question, experiment_question, reading_passage_question. Use null when not explicit; deterministic post-processing will infer from neighboring structure.
   - format describes answer form, e.g. multiple_choice, true_false, fill_blank, short_answer, essay, numeric_problem, word_problem, matching, ordering, classification, comparison, explain, justify, prove, derive, calculate, label_diagram, interpret_graph, interpret_table, interpret_map, image_question, reading_comprehension, grammar_question, vocabulary_question, open_ended. It is open-ended: use a precise new value if needed.
   - purpose describes educational intent, e.g. recall, understanding, application, problem_solving, critical_thinking, analysis, evaluation, creation, assessment.
   - bloom_level may be remember, understand, apply, analyze, evaluate, create when supported.
   - group_title is the visible heading such as "أسئلة الدرس", "تحقق من فهمك", "Chapter Review", or "Unit Questions".
   - For compound questions such as 5(a)(b)(c) or 5-أ/ب/ج, keep the parent question and put each independently answerable subquestion in children. Never merge materially different subquestions into one stem.
   - references should record explicitly referenced figure/graph/table/map/passage/equation labels or page numbers.
   - visible_answer must be null unless the answer is explicitly printed. Never solve a question.
7. Any educationally meaningful visual region must become its own visual block using map/figure/diagram/graph/chart/table/image/timeline as the nearest broad type. Use subtype freely when useful. The later visual pipeline will do deep open-ended classification.
8. For visual blocks, extract only visible text/caption/figure label and an objective shallow description. Do not deeply infer meaning at page level.
9. Do not omit non-scientific content: literature, languages, religion/culture, history, art, economics, computing, geography, mathematics, sciences, vocational books, and unfamiliar subjects are all valid.
10. Preserve mathematical notation, Arabic punctuation, Latin symbols, units, superscripts/subscripts as faithfully as possible.
11. page_language can be ar, en, mixed, or another visible language.
12. confidence is extraction confidence, not truth probability.
"""


VISUAL_SYSTEM = """You are a universal visual-document analyst for educational books. You analyze ONE CROPPED VISUAL ASSET at a time. It may be any kind of visual from any subject: photo, illustration, map, chart, graph, table, geometry figure, circuit, chemical structure, process diagram, timeline, manuscript, artwork, infographic, screenshot, symbol set, or an unknown future type. Do not rely on a closed taxonomy. Separate what is directly visible from what is supplied only by surrounding context. Never add external factual knowledge. Return strict JSON only."""


def visual_asset_prompt(
    asset_id: str,
    broad_type: str,
    page_number: int,
    printed_page_number: str | None,
    block_title: str | None,
    block_caption: str | None,
    block_text: str,
    context: str,
    book_meta: dict,
    retry_feedback: str | None = None,
) -> str:
    feedback = f"\nPrevious verifier feedback to correct:\n{retry_feedback}\n" if retry_feedback else ""
    return f"""
Asset ID: {asset_id}
Broad page-level type: {broad_type}
PDF page: {page_number}
Printed page: {printed_page_number}
Book metadata: {json.dumps(book_meta, ensure_ascii=False)}
Page-level title: {block_title}
Page-level caption: {block_caption}
Visible text previously noticed in this asset: {block_text[:5000]}
{feedback}
Context from the same/neighboring textbook pages. This context may help interpretation, but it is NOT necessarily visible inside the crop:
---BEGIN CONTEXT---
{context[:16000]}
---END CONTEXT---

Analyze the supplied CROP deeply and return exactly this shape:
{{
  "visual_type": "open-ended type name",
  "visual_subtype": null,
  "title": null,
  "caption": null,
  "figure_label": null,
  "languages": [],
  "summary": null,
  "educational_role": null,
  "visible_text": [
    {{"text":"", "bbox":null, "language":null, "role":null, "confidence":0.0, "evidence":[{{"source":"visible_visual","detail":null,"confidence":0.0}}]}}
  ],
  "labels": [],
  "entities": [
    {{"id":"obj1", "entity_type":"", "name":null, "label":null, "bbox":null, "attributes":{{}}, "confidence":0.0, "evidence":[]}}
  ],
  "regions": [],
  "arrows": [
    {{"id":"arrow1", "source_id":null, "target_id":null, "label":null, "direction":null, "bbox":null, "confidence":0.0}}
  ],
  "relationships": [
    {{"source_id":"obj1", "target_id":"obj2", "relation":"", "direction":null, "label":null, "confidence":0.0, "evidence":[]}}
  ],
  "legend": [{{"marker":null,"meaning":null,"bbox":null,"confidence":0.0}}],
  "axes": [{{"orientation":null,"label":null,"unit":null,"minimum":null,"maximum":null,"tick_labels":[],"confidence":0.0}}],
  "measurements": [{{"name":null,"value":null,"unit":null,"applies_to":null,"confidence":0.0}}],
  "steps": [{{"order":null,"label":null,"description":"","entity_ids":[],"confidence":0.0}}],
  "colors_with_meaning": [{{"color_or_pattern":"","meaning":null,"confidence":0.0}}],
  "symbols": [],
  "equations": [],
  "data_points": [],
  "concepts": [],
  "keywords": [],
  "raw_attributes": {{}},
  "confidence_by_field": {{}},
  "overall_confidence": 0.0,
  "verification": {{"status":"unverified","confidence":0.0,"supported_claims":[],"unsupported_claims":[],"contradictions":[],"notes":[]}}
}}

Universal rules:
1. visual_type is OPEN ENDED. Choose the most precise neutral type visible in the crop. If unfamiliar, use a descriptive type rather than forcing it into biology/geography/etc.
2. Coordinates in this response are normalized 0..1000 relative to the CROPPED ASSET, not the full page.
3. visible_text and labels must contain only text actually visible in the crop. Preserve Arabic/English wording exactly.
4. Context may support summary/educational_role/concepts, but never report context-only text as visible_text.
5. entities are visible objects, components, regions, nodes, shapes, landmarks, characters, symbols, plotted series, cells, devices, geometric objects, etc. Use generic entity types when uncertain.
6. relationships capture arrows, containment, adjacency, connection, sequence, comparison, correspondence, labeled-part relations, spatial relations, or any explicitly supported relation.
7. For maps: capture visible labels, legend, scale/north indicators if present, regions/features, symbols, and meaningful color/pattern encoding. Do not guess an unlabeled place.
8. For charts/graphs: capture axes, units, legend, visible series/entities, labeled data points, and visually supported trends. Do not fabricate numeric values that are not legible.
9. For tables: use visible_text/entities/raw_attributes to preserve headers/cells/structure; do not invent missing cells.
10. For diagrams/processes/timelines: capture nodes/entities, arrows, sequence/steps and labels.
11. For geometry/mathematics: capture points, lines, shapes, angles, lengths, coordinate labels, equations, and relationships only when visible.
12. For chemistry/physics/computing/engineering: capture symbols, components, connections, labels, formulas and measurements only when visible.
13. For photographs/art/literature/history: objectively describe visible composition and link educational_role only when supported by caption/context.
14. Every inferential claim should be conservative. Use evidence source values such as visible_visual, visible_text, caption, surrounding_text, pdf_text_layer, or model_inference.
15. Never identify a person/place/species/object with certainty solely from appearance when the crop/context does not explicitly support it.
"""


VISUAL_VERIFY_SYSTEM = """You are an adversarial verifier for textbook visual extraction. Check whether the proposed structured analysis is supported by the supplied crop and textbook context. Your job is to catch hallucinated labels, invented relationships, wrong chart/map readings, and context being falsely reported as visible. Return strict JSON only."""


def visual_verify_prompt(asset_id: str, analysis: dict, context: str) -> str:
    return f"""
Asset ID: {asset_id}
Proposed analysis:
{json.dumps(analysis, ensure_ascii=False)[:24000]}

Textbook context:
---BEGIN CONTEXT---
{context[:12000]}
---END CONTEXT---

Inspect the supplied crop and verify the proposed analysis.
Return exactly:
{{
  "status": "passed|uncertain|needs_retry|failed",
  "confidence": 0.0,
  "supported_claims": [],
  "unsupported_claims": [],
  "contradictions": [],
  "notes": []
}}

Rules:
- passed means no material unsupported claim was found.
- needs_retry means the analysis is useful but contains material errors that a second extraction pass should correct.
- uncertain means the crop is too ambiguous/low-resolution to verify important details.
- failed means the analysis is substantially unreliable.
- Treat visible labels/text as exact evidence: do not accept invented wording.
- Context can support interpretation but cannot make a context-only label become visually present.
"""

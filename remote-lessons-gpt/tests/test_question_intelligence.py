from remote_lessons_gpt.question_intelligence import QuestionIntelligenceEngine
from remote_lessons_gpt.schemas import ContentType, ExtractedBlock, PageExtraction, QuestionData


def test_arabic_lesson_end_question_classification():
    page = PageExtraction(
        pdf_page_number=10,
        explicit_lesson_title="القوة والحركة",
        blocks=[
            ExtractedBlock(
                sequence=1,
                content_type=ContentType.SECTION_HEADING,
                verbatim_text="أسئلة الدرس",
            ),
            ExtractedBlock(
                sequence=2,
                content_type=ContentType.LESSON_QUESTION,
                verbatim_text="1. علل: تزداد سرعة الجسم عند زيادة القوة المؤثرة فيه.",
                question=QuestionData(number="1", stem="علل: تزداد سرعة الجسم عند زيادة القوة المؤثرة فيه."),
            ),
        ],
    )

    QuestionIntelligenceEngine().enrich_pages([page])
    block = page.blocks[1]
    assert block.content_type == ContentType.QUESTION
    assert block.question.scope == "lesson_end"
    assert block.question.group_title == "أسئلة الدرس"
    assert block.question.format == "justify"
    assert block.question.purpose == "understanding"
    assert block.question.bloom_level == "understand"
    assert block.question.classification_confidence >= 0.9


def test_english_checkpoint_multiple_choice():
    page = PageExtraction(
        pdf_page_number=3,
        blocks=[
            ExtractedBlock(sequence=1, content_type=ContentType.SECTION_HEADING, verbatim_text="Check your understanding"),
            ExtractedBlock(
                sequence=2,
                content_type=ContentType.MULTIPLE_CHOICE,
                verbatim_text="Which organ pumps blood around the body?",
                question=QuestionData(
                    number="2",
                    stem="Which organ pumps blood around the body?",
                    choices=["Lung", "Heart", "Kidney", "Liver"],
                ),
            ),
        ],
    )

    QuestionIntelligenceEngine().enrich_pages([page])
    q = page.blocks[1].question
    assert q.scope == "checkpoint"
    assert q.format == "multiple_choice"
    assert q.group_title == "Check your understanding"


def test_structural_lesson_end_inference_from_next_lesson():
    p1 = PageExtraction(
        pdf_page_number=20,
        blocks=[
            ExtractedBlock(sequence=1, content_type=ContentType.EXPLANATION, verbatim_text="Lesson content."),
            ExtractedBlock(
                sequence=2,
                content_type=ContentType.QUESTION,
                verbatim_text="1. Explain what happens when the force doubles.",
                question=QuestionData(number="1", stem="Explain what happens when the force doubles."),
            ),
        ],
    )
    p2 = PageExtraction(pdf_page_number=21, explicit_lesson_title="A New Lesson", blocks=[])

    QuestionIntelligenceEngine().enrich_pages([p1, p2])
    assert p1.blocks[1].question.scope == "lesson_end"
    assert any("neighboring_hierarchy" in x for x in p1.blocks[1].question.classification_evidence)


def test_compound_questions_keep_independent_children():
    page = PageExtraction(
        pdf_page_number=30,
        blocks=[
            ExtractedBlock(sequence=1, content_type=ContentType.SECTION_HEADING, verbatim_text="مراجعة الوحدة"),
            ExtractedBlock(
                sequence=2,
                content_type=ContentType.QUESTION,
                verbatim_text="5. أجب عما يلي",
                question=QuestionData(
                    number="5",
                    stem="أجب عما يلي",
                    children=[
                        QuestionData(sub_number="أ", stem="احسب سرعة الجسم."),
                        QuestionData(sub_number="ب", stem="فسر النتيجة."),
                    ],
                ),
            ),
        ],
    )

    QuestionIntelligenceEngine().enrich_pages([page])
    parent = page.blocks[1].question
    assert parent.scope == "unit_end"
    assert parent.children[0].scope == "unit_end"
    assert parent.children[0].format == "calculate"
    assert parent.children[0].bloom_level == "apply"
    assert parent.children[1].format == "explain"
    assert parent.children[1].bloom_level == "understand"


def test_visual_question_dependencies_are_detected():
    page = PageExtraction(
        pdf_page_number=40,
        blocks=[
            ExtractedBlock(
                sequence=1,
                content_type=ContentType.QUESTION,
                verbatim_text="بالاعتماد على الرسم البياني 3-2، حدد أعلى قيمة ثم فسر الاتجاه.",
                question=QuestionData(number="3", stem="بالاعتماد على الرسم البياني 3-2، حدد أعلى قيمة ثم فسر الاتجاه."),
            )
        ],
    )
    QuestionIntelligenceEngine().enrich_pages([page])
    q = page.blocks[0].question
    assert q.requires_visual is True
    assert q.requires_graph is True
    assert any(r.reference_type == "graph" for r in q.references)
    assert any(r.figure_label == "3-2" for r in q.references if r.reference_type == "graph")

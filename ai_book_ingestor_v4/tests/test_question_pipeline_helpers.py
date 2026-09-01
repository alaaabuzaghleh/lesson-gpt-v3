from book_ingestor.pipeline import BookIngestionPipeline
from book_ingestor.schemas import IndexDocument, QuestionData, QuestionReference


def _base_doc(**overrides):
    data = dict(
        id="doc-parent",
        book_id="book1",
        book_title="Science",
        pdf_page_number=12,
        printed_page_number="10",
        sequence=4,
        content_type="question",
        text="Answer the following",
        normalized_text="answer the following",
        search_text="answer the following",
        confidence=0.95,
        quality_score=0.9,
    )
    data.update(overrides)
    return IndexDocument(**data)


def test_compound_question_is_flattened_into_searchable_child_docs():
    pipeline = BookIngestionPipeline.__new__(BookIngestionPipeline)
    parent = QuestionData(
        number="5",
        scope="lesson_end",
        group_title="Lesson Questions",
        children=[
            QuestionData(sub_number="a", stem="Calculate the speed.", format="calculate", bloom_level="apply", classification_confidence=0.9),
            QuestionData(sub_number="b", stem="Explain the result.", format="explain", bloom_level="understand", classification_confidence=0.9),
        ],
    )
    pipeline._assign_question_ids(parent, "book1", 12, 4)
    base = _base_doc(question=parent.model_dump(mode="json"), question_id=parent.question_id)

    children = pipeline._expand_subquestions(base, parent)
    assert len(children) == 2
    assert children[0].question_parent_id == parent.question_id
    assert children[0].question_number == "a"
    assert children[0].question_format == "calculate"
    assert children[1].question_format == "explain"
    assert children[0].content_type == "question"
    assert children[0].subtype == "subquestion"


def test_question_reference_resolves_to_matching_visual_asset():
    pipeline = BookIngestionPipeline.__new__(BookIngestionPipeline)
    q = QuestionData(
        question_id="book1-p0012-q004",
        number="4",
        stem="Use Figure 3-2 to answer.",
        requires_visual=True,
        references=[QuestionReference(reference_type="figure", figure_label="3-2", reference_text="Figure 3-2")],
    )
    qdoc = _base_doc(question=q.model_dump(mode="json"), question_id=q.question_id, question_requires_visual=True)
    visual = IndexDocument(
        id="visual-doc",
        book_id="book1",
        book_title="Science",
        pdf_page_number=12,
        printed_page_number="10",
        sequence=3,
        content_type="figure",
        text="",
        normalized_text="",
        search_text="",
        asset_id="book1-p0012-a003",
        visual_type="figure",
        figure_label="Figure 3-2",
        confidence=0.95,
        quality_score=0.95,
    )

    docs = [visual, qdoc]
    pipeline._link_question_references(docs)
    assert qdoc.question_reference_ids == ["book1-p0012-a003"]
    assert qdoc.question["references"][0]["target_id"] == "book1-p0012-a003"

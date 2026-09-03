from book_ingestor.quality import block_quality_score, ocr_completeness, ocr_page_is_sparse
from book_ingestor.schemas import ExtractedBlock, ContentType, QuestionData


def test_answer_hallucination_penalty():
    b = ExtractedBlock(
        sequence=1,
        content_type=ContentType.LESSON_QUESTION,
        verbatim_text="ما تعريف القوة؟",
        confidence=0.9,
        question=QuestionData(number="1", stem="ما تعريف القوة؟", visible_answer="جواب مخترع", answer_is_explicitly_visible=False),
    )
    assert block_quality_score(b) < 0.8


def test_ocr_completeness_requires_every_page():
    assert ocr_page_is_sparse("", 0, min_chars=20)
    assert not ocr_page_is_sparse("قانون نيوتن الثاني للحركة", 1, min_chars=20)
    stats = ocr_completeness(
        start_page=1,
        end_page=3,
        ocr_pages={1, 2},
        empty_pages=[],
        sparse_pages=[],
        failed_pages=[],
    )
    assert stats["ocr_coverage"] < 1
    assert stats["missing_ocr_pages"] == [3]
    assert stats["ocr_complete"] is False
    complete = ocr_completeness(
        start_page=1,
        end_page=2,
        ocr_pages={1, 2},
        empty_pages=[],
        sparse_pages=[],
        failed_pages=[],
    )
    assert complete["ocr_complete"] is True
    assert complete["recommended_for_live_index"] is True

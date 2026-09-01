from book_ingestor.quality import block_quality_score
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

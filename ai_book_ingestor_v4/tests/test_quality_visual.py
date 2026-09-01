from book_ingestor.quality import block_quality_score
from book_ingestor.schemas import BBox, ContentType, ExtractedBlock, VisualAnalysis, VisualVerification


def _block():
    return ExtractedBlock(
        sequence=1,
        content_type=ContentType.IMAGE,
        verbatim_text="Figure 1 الشكل 1",
        bbox=BBox(x1=10, y1=10, x2=900, y2=900),
        caption="Figure 1",
        confidence=0.9,
    )


def test_passed_visual_scores_higher_than_failed_visual():
    good = VisualAnalysis(
        visual_type="diagram",
        summary="Visible labeled diagram",
        overall_confidence=0.9,
        verification=VisualVerification(status="passed", confidence=0.95),
    )
    bad = VisualAnalysis(
        visual_type="diagram",
        summary="Unreliable diagram",
        overall_confidence=0.9,
        verification=VisualVerification(status="failed", confidence=0.95),
    )
    assert block_quality_score(_block(), good) > block_quality_score(_block(), bad)

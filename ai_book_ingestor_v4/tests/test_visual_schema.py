from book_ingestor.schemas import BBox, EvidenceRef, VisualAnalysis, VisualEntity, VisualVerification


def test_general_visual_schema_supports_unknown_types():
    v = VisualAnalysis(
        visual_type="genealogy_tree",
        visual_subtype="family_relationship_chart",
        entities=[
            VisualEntity(
                id="obj1",
                entity_type="node",
                name="أحمد",
                bbox=BBox(x1=10, y1=10, x2=200, y2=100),
                evidence=[EvidenceRef(source="visible_text", confidence=0.99)],
            )
        ],
        concepts=["family relationships", "العلاقات الأسرية"],
        overall_confidence=0.9,
        verification=VisualVerification(status="passed", confidence=0.95),
    )
    assert v.visual_type == "genealogy_tree"
    assert v.entities[0].name == "أحمد"
    assert v.verification.status == "passed"

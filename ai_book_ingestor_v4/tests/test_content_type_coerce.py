from book_ingestor.schemas import ContentType, ExtractedBlock, PageExtraction, coerce_content_type


def test_title_alias_maps_to_section_heading():
    assert coerce_content_type("title") == ContentType.SECTION_HEADING
    block = ExtractedBlock(sequence=1, content_type="title", verbatim_text="العلاقات والدوال")
    assert block.content_type == ContentType.SECTION_HEADING
    assert block.subtype == "title"


def test_unknown_content_type_falls_back_to_other():
    block = ExtractedBlock(sequence=1, content_type="banner", verbatim_text="شعار")
    assert block.content_type == ContentType.OTHER
    assert block.subtype == "banner"


def test_page_extraction_accepts_title_blocks():
    page = PageExtraction.model_validate({
        "pdf_page_number": 3,
        "blocks": [{"sequence": 1, "content_type": "title", "verbatim_text": "الوحدة الأولى"}],
    })
    assert page.blocks[0].content_type == ContentType.SECTION_HEADING

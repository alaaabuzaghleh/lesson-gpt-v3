from remote_lessons_gpt.opensearch_index import INDEX_BODY


def test_question_fields_are_searchable_in_opensearch_mapping():
    props = INDEX_BODY["mappings"]["properties"]
    required = {
        "question_id",
        "question_parent_id",
        "question_number",
        "question_group",
        "question_scope",
        "question_format",
        "question_purpose",
        "question_bloom_level",
        "question_difficulty",
        "question_requires_visual",
        "question_reference_ids",
        "question_reference_text",
    }
    assert required.issubset(props)
    assert props["question_scope"]["type"] == "keyword"
    assert props["question_group"]["fields"]["ar"]["analyzer"] == "arabic"
    assert props["question_group"]["fields"]["en"]["analyzer"] == "english"
    assert "ocr_text" in props
    assert props["ocr_text"]["fields"]["ar"]["analyzer"] == "arabic"
    assert props["ocr_source"]["type"] == "keyword"
    assert props["text_source"]["type"] == "keyword"

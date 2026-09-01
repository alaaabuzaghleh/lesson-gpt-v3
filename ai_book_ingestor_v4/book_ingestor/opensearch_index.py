from __future__ import annotations

from urllib.parse import urlparse
try:
    from opensearchpy import OpenSearch, helpers
except ImportError:  # Keep extraction/tests usable before optional search dependency is installed.
    OpenSearch = None  # type: ignore[assignment]
    helpers = None  # type: ignore[assignment]

from .config import settings


def create_client():
    if OpenSearch is None:
        raise RuntimeError("opensearch-py is not installed. Run: pip install -r requirements.txt")
    url = urlparse(settings.opensearch_url)
    auth = None
    if settings.opensearch_username:
        auth = (settings.opensearch_username, settings.opensearch_password)
    return OpenSearch(
        hosts=[{"host": url.hostname or "localhost", "port": url.port or (443 if url.scheme == "https" else 9200)}],
        http_auth=auth,
        use_ssl=url.scheme == "https",
        verify_certs=settings.opensearch_verify_certs,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


MULTILINGUAL_TEXT = {
    "type": "text",
    "fields": {
        "ar": {"type": "text", "analyzer": "arabic"},
        "en": {"type": "text", "analyzer": "english"},
    },
}

MULTILINGUAL_TEXT_RAW = {
    "type": "text",
    "fields": {
        "ar": {"type": "text", "analyzer": "arabic"},
        "en": {"type": "text", "analyzer": "english"},
        "raw": {"type": "keyword", "ignore_above": 1024},
    },
}

INDEX_BODY = {
    "settings": {
        "index": {"number_of_shards": 1, "number_of_replicas": 0},
        "analysis": {
            "normalizer": {
                "lc_normalizer": {
                    "type": "custom",
                    "filter": ["lowercase", "asciifolding"],
                }
            }
        },
    },
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "id": {"type": "keyword"},
            "book_id": {"type": "keyword"},
            "book_title": MULTILINGUAL_TEXT_RAW,
            "country": {"type": "keyword", "normalizer": "lc_normalizer"},
            "curriculum": {"type": "keyword", "normalizer": "lc_normalizer"},
            "education_system": {"type": "keyword", "normalizer": "lc_normalizer"},
            "grade": {"type": "keyword", "normalizer": "lc_normalizer"},
            "subject": {"type": "keyword", "normalizer": "lc_normalizer"},
            "semester": {"type": "keyword", "normalizer": "lc_normalizer"},
            "academic_year": {"type": "keyword"},
            "language": {"type": "keyword"},
            "pdf_page_number": {"type": "integer"},
            "printed_page_number": {"type": "keyword"},
            "unit_title": MULTILINGUAL_TEXT_RAW,
            "chapter_title": MULTILINGUAL_TEXT_RAW,
            "lesson_title": MULTILINGUAL_TEXT_RAW,
            "section_title": MULTILINGUAL_TEXT_RAW,
            "hierarchy_path": {"type": "keyword"},
            "sequence": {"type": "integer"},
            "content_type": {"type": "keyword"},
            "subtype": {"type": "keyword"},
            "title": MULTILINGUAL_TEXT_RAW,
            "text": MULTILINGUAL_TEXT,
            "normalized_text": {"type": "text"},
            "search_text": MULTILINGUAL_TEXT,
            "concepts": MULTILINGUAL_TEXT_RAW,
            "keywords": MULTILINGUAL_TEXT_RAW,
            "aliases": MULTILINGUAL_TEXT,
            "skills": {"type": "keyword"},
            "prerequisites": MULTILINGUAL_TEXT,
            "difficulty": {"type": "keyword"},
            "bloom_level": {"type": "keyword"},
            "importance": {"type": "keyword"},
            "question": {"type": "object", "enabled": False},
            "question_id": {"type": "keyword"},
            "question_parent_id": {"type": "keyword"},
            "question_number": {"type": "keyword"},
            "question_group": MULTILINGUAL_TEXT_RAW,
            "question_scope": {"type": "keyword"},
            "question_format": {"type": "keyword"},
            "question_purpose": {"type": "keyword"},
            "question_bloom_level": {"type": "keyword"},
            "question_difficulty": {"type": "keyword"},
            "question_requires_visual": {"type": "boolean"},
            "question_requires_table": {"type": "boolean"},
            "question_requires_graph": {"type": "boolean"},
            "question_requires_map": {"type": "boolean"},
            "question_requires_passage": {"type": "boolean"},
            "question_requires_equation": {"type": "boolean"},
            "question_reference_ids": {"type": "keyword"},
            "question_reference_text": MULTILINGUAL_TEXT,
            "graph": {"type": "object", "enabled": False},
            "table": {"type": "object", "enabled": False},
            "figure_label": {"type": "keyword"},
            "caption": MULTILINGUAL_TEXT,
            "cross_references": {"type": "keyword"},

            "asset_id": {"type": "keyword"},
            "visual_type": {"type": "keyword"},
            "visual_subtype": {"type": "keyword"},
            "visual_summary": MULTILINGUAL_TEXT,
            "visual_text": MULTILINGUAL_TEXT,
            "visual_labels": MULTILINGUAL_TEXT_RAW,
            "visual_concepts": MULTILINGUAL_TEXT_RAW,
            "visual_verification_status": {"type": "keyword"},
            "visual_analysis": {"type": "object", "enabled": False},

            "bbox": {"type": "object", "enabled": False},
            "asset_path": {"type": "keyword", "index": False},
            "page_image_path": {"type": "keyword", "index": False},
            "source_pdf_path": {"type": "keyword", "index": False},
            "confidence": {"type": "float"},
            "quality_score": {"type": "float"},
            "extraction_notes": {"type": "text", "index": False},
        },
    },
}


def ensure_index(client, index_name: str, recreate: bool = False):
    if client.indices.exists(index=index_name):
        if not recreate:
            return
        client.indices.delete(index=index_name)
    client.indices.create(index=index_name, body=INDEX_BODY)


def bulk_index(client, index_name: str, docs: list[dict], refresh: bool = True):
    if helpers is None:
        raise RuntimeError("opensearch-py is not installed. Run: pip install -r requirements.txt")
    actions = [
        {"_op_type": "index", "_index": index_name, "_id": doc["id"], "_source": doc}
        for doc in docs
    ]
    success, errors = helpers.bulk(client, actions, raise_on_error=False, refresh=refresh)
    return success, errors

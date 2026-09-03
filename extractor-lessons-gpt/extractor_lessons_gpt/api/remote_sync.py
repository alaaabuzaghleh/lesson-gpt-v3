from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from remote_lessons_gpt.opensearch_index import bulk_index, create_client, ensure_index

from extractor_lessons_gpt.config import settings


def remote_opensearch_configured() -> bool:
    return bool(settings.remote_opensearch_url.strip())


def _remote_client():
    if not remote_opensearch_configured():
        raise RuntimeError("REMOTE_OPENSEARCH_URL is not configured")
    try:
        from opensearchpy import OpenSearch
    except ImportError as exc:
        raise RuntimeError("opensearch-py is not installed") from exc

    url = urlparse(settings.remote_opensearch_url)
    auth = None
    if settings.remote_opensearch_username:
        auth = (settings.remote_opensearch_username, settings.remote_opensearch_password)
    return OpenSearch(
        hosts=[{"host": url.hostname or "localhost", "port": url.port or (443 if url.scheme == "https" else 9200)}],
        http_auth=auth,
        use_ssl=url.scheme == "https",
        verify_certs=settings.remote_opensearch_verify_certs,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


def sync_documents_to_remote(
    documents: list[dict[str, Any]],
    *,
    recreate_index: bool = False,
) -> tuple[int, list[Any]]:
    if not documents:
        return 0, []
    client = _remote_client()
    index_name = settings.remote_opensearch_index or settings.opensearch_index
    ensure_index(client, index_name, recreate=recreate_index)
    return bulk_index(client, index_name, documents, refresh=True)


def sync_book_documents_from_local(
    book_id: str,
    *,
    recreate_index: bool = False,
) -> tuple[int, list[Any]]:
    os.environ.setdefault("OPENSEARCH_URL", settings.opensearch_url)
    local_client = create_client()
    index_name = settings.opensearch_index
    body = {
        "size": 5000,
        "query": {"term": {"book_id": book_id}},
        "sort": [{"pdf_page_number": "asc"}, {"sequence": "asc"}],
    }
    response = local_client.search(index=index_name, body=body)
    documents = [hit["_source"] for hit in response["hits"]["hits"]]
    return sync_documents_to_remote(documents, recreate_index=recreate_index)

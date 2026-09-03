from __future__ import annotations

from typing import Any
from .normalizer import normalize_general


class BookSearchService:
    def __init__(self, client, index_name: str):
        self.client = client
        self.index_name = index_name

    @staticmethod
    def _term_filters(filters: dict[str, Any] | None) -> list[dict]:
        clauses: list[dict] = []
        for field, value in (filters or {}).items():
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                clauses.append({"terms": {field: list(value)}})
            else:
                clauses.append({"term": {field: value}})
        return clauses

    def search(self, query: str, filters: dict[str, Any] | None = None, size: int = 15) -> list[dict]:
        nq = normalize_general(query)
        body = {
            "size": size,
            "track_total_hits": True,
            "query": {
                "bool": {
                    "filter": self._term_filters(filters),
                    "should": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "title^8", "title.ar^8", "title.en^8",
                                    "lesson_title^6", "lesson_title.ar^6", "lesson_title.en^6",
                                    "chapter_title^4", "unit_title^3",
                                    "concepts^5", "keywords^5", "aliases^3",
                                    "visual_labels^7", "visual_labels.ar^7", "visual_labels.en^7",
                                    "visual_concepts^5", "visual_summary^4", "visual_text^4",
                                    "question_group^6", "question_group.ar^6", "question_group.en^6",
                                    "question_reference_text^5", "question_reference_text.ar^5", "question_reference_text.en^5",
                                    "caption^3", "text^2", "text.ar^2", "text.en^2",
                                    "ocr_text^3", "ocr_text.ar^3", "ocr_text.en^3",
                                ],
                                "type": "best_fields",
                                "operator": "or",
                            }
                        },
                        {"match_phrase": {"text": {"query": query, "boost": 4}}},
                        {"match_phrase": {"title": {"query": query, "boost": 8}}},
                        {"match_phrase": {"visual_text": {"query": query, "boost": 6}}},
                        {"match_phrase": {"ocr_text": {"query": query, "boost": 5}}},
                        {"match": {"normalized_text": {"query": nq, "boost": 2}}},
                        {"match": {"search_text": {"query": nq, "boost": 2}}},
                    ],
                    "minimum_should_match": 1,
                }
            },
            "sort": ["_score", {"quality_score": "desc"}, {"pdf_page_number": "asc"}],
        }
        response = self.client.search(index=self.index_name, body=body)
        return [{"score": hit.get("_score"), **hit["_source"]} for hit in response["hits"]["hits"]]

    def exact_page(self, book_id: str, page: str | int, size: int = 300) -> list[dict]:
        page_str = str(page)
        body = {
            "size": size,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"book_id": book_id}},
                        {
                            "bool": {
                                "should": [
                                    {"term": {"printed_page_number": page_str}},
                                    {"term": {"pdf_page_number": int(page)}} if page_str.isdigit() else {"match_none": {}},
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                    ]
                }
            },
            "sort": [{"pdf_page_number": "asc"}, {"sequence": "asc"}],
        }
        r = self.client.search(index=self.index_name, body=body)
        return [hit["_source"] for hit in r["hits"]["hits"]]

    def find_question(self, book_id: str, page: str | int, question_number: str) -> list[dict]:
        """Find a parent or subquestion on a printed/PDF page.

        Accepts forms such as 5, 5-b, 5 ب, ب. Flattened subquestions are searched
        independently while legacy nested records remain supported.
        """
        results = self.exact_page(book_id, page)
        qn = normalize_general(str(question_number)).replace("-", " ")
        parent_numbers = {
            d.get("question_id"): (d.get("question") or {}).get("number")
            for d in results
            if d.get("question_id") and not d.get("question_parent_id")
        }
        found = []
        for doc in results:
            q = doc.get("question") or {}
            parent_no = parent_numbers.get(doc.get("question_parent_id"))
            composite = " ".join(str(x) for x in [parent_no, q.get("sub_number") or doc.get("question_number")] if x)
            candidates = [
                doc.get("question_number"),
                q.get("number"),
                q.get("sub_number"),
                " ".join(str(x) for x in [q.get("number"), q.get("sub_number")] if x),
                composite,
                doc.get("question_id"),
            ]
            normalized = [normalize_general(str(x or "")).replace("-", " ") for x in candidates]
            if qn in normalized or any(x.endswith(" " + qn) for x in normalized if x):
                found.append(doc)
        return found

    def find_questions(
        self,
        book_id: str,
        query: str | None = None,
        scope: str | None = None,
        question_format: str | None = None,
        purpose: str | None = None,
        bloom_level: str | None = None,
        difficulty: str | None = None,
        lesson_title: str | None = None,
        chapter_title: str | None = None,
        unit_title: str | None = None,
        requires_visual: bool | None = None,
        size: int = 100,
    ) -> list[dict]:
        filters: list[dict] = [
            {"term": {"book_id": book_id}},
            {"term": {"content_type": "question"}},
        ]
        if scope:
            filters.append({"term": {"question_scope": scope}})
        if question_format:
            filters.append({"term": {"question_format": question_format}})
        if purpose:
            filters.append({"term": {"question_purpose": purpose}})
        if bloom_level:
            filters.append({"term": {"question_bloom_level": bloom_level}})
        if difficulty:
            filters.append({"term": {"question_difficulty": difficulty}})
        if lesson_title:
            filters.append({"term": {"lesson_title.raw": lesson_title}})
        if chapter_title:
            filters.append({"term": {"chapter_title.raw": chapter_title}})
        if unit_title:
            filters.append({"term": {"unit_title.raw": unit_title}})
        if requires_visual is not None:
            filters.append({"term": {"question_requires_visual": requires_visual}})

        must: list[dict] = []
        if query:
            must.append({
                "multi_match": {
                    "query": query,
                    "fields": [
                        "text^5", "text.ar^5", "text.en^5",
                        "question_group^4", "question_reference_text^4",
                        "lesson_title^3", "concepts^3", "keywords^3", "search_text^2",
                    ],
                    "operator": "or",
                }
            })

        body = {
            "size": size,
            "query": {"bool": {"filter": filters, "must": must}},
            "sort": (["_score", {"pdf_page_number": "asc"}, {"sequence": "asc"}] if query else [{"pdf_page_number": "asc"}, {"sequence": "asc"}]),
        }
        r = self.client.search(index=self.index_name, body=body)
        return [{"score": hit.get("_score"), **hit["_source"]} for hit in r["hits"]["hits"]]

    def get_question_context(self, question_id: str, radius: int = 2) -> dict | None:
        body = {"size": 1, "query": {"term": {"question_id": question_id}}}
        r = self.client.search(index=self.index_name, body=body)
        hits = r["hits"]["hits"]
        if not hits:
            return None
        question_doc = hits[0]["_source"]
        refs = []
        for target in question_doc.get("question_reference_ids") or []:
            asset_body = {
                "size": 1,
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"asset_id": target}},
                            {"term": {"id": target}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
            }
            ar = self.client.search(index=self.index_name, body=asset_body)
            if ar["hits"]["hits"]:
                refs.append(ar["hits"]["hits"][0]["_source"])
        adjacent = self.adjacent_blocks(
            question_doc["book_id"], question_doc["pdf_page_number"], question_doc["sequence"], radius=radius
        )
        return {"question": question_doc, "references": refs, "adjacent_blocks": adjacent}

    def find_visuals(
        self,
        book_id: str,
        page: str | int | None = None,
        visual_type: str | None = None,
        query: str | None = None,
        size: int = 50,
    ) -> list[dict]:
        filters: list[dict] = [{"term": {"book_id": book_id}}, {"exists": {"field": "asset_id"}}]
        if visual_type:
            filters.append({"term": {"visual_type": visual_type}})
        if page is not None:
            page_str = str(page)
            filters.append({
                "bool": {
                    "should": [
                        {"term": {"printed_page_number": page_str}},
                        {"term": {"pdf_page_number": int(page)}} if page_str.isdigit() else {"match_none": {}},
                    ],
                    "minimum_should_match": 1,
                }
            })
        must = []
        if query:
            must.append({
                "multi_match": {
                    "query": query,
                    "fields": ["visual_labels^7", "visual_text^6", "visual_summary^4", "visual_concepts^5", "caption^3", "text^2"],
                }
            })
        body = {
            "size": size,
            "query": {"bool": {"filter": filters, "must": must}},
            "sort": (["_score", {"quality_score": "desc"}] if query else [{"pdf_page_number": "asc"}, {"sequence": "asc"}]),
        }
        r = self.client.search(index=self.index_name, body=body)
        return [{"score": hit.get("_score"), **hit["_source"]} for hit in r["hits"]["hits"]]
    def get_asset(self, asset_id: str) -> dict | None:
        body = {
            "size": 1,
            "query": {"term": {"asset_id": asset_id}},
        }
        r = self.client.search(index=self.index_name, body=body)
        hits = r["hits"]["hits"]
        return hits[0]["_source"] if hits else None

    def get_lesson(self, book_id: str, lesson_title: str, size: int = 1000) -> list[dict]:
        body = {
            "size": size,
            "query": {
                "bool": {
                    "filter": [{"term": {"book_id": book_id}}],
                    "must": [{"term": {"lesson_title.raw": lesson_title}}],
                }
            },
            "sort": [{"pdf_page_number": "asc"}, {"sequence": "asc"}],
        }
        r = self.client.search(index=self.index_name, body=body)
        return [hit["_source"] for hit in r["hits"]["hits"]]

    def adjacent_blocks(self, book_id: str, pdf_page_number: int, sequence: int, radius: int = 1) -> list[dict]:
        # Fetch nearby pages then order deterministically. This also works across page boundaries.
        body = {
            "size": 1000,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"book_id": book_id}},
                        {"range": {"pdf_page_number": {"gte": max(1, pdf_page_number - 1), "lte": pdf_page_number + 1}}},
                    ]
                }
            },
            "sort": [{"pdf_page_number": "asc"}, {"sequence": "asc"}],
        }
        r = self.client.search(index=self.index_name, body=body)
        docs = [hit["_source"] for hit in r["hits"]["hits"]]
        pos = next((i for i, d in enumerate(docs) if d.get("pdf_page_number") == pdf_page_number and d.get("sequence") == sequence), None)
        if pos is None:
            return []
        lo = max(0, pos - radius)
        hi = min(len(docs), pos + radius + 1)
        return docs[lo:hi]


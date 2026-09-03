from __future__ import annotations

from typing import Any

import httpx

from extractor_lessons_gpt.config import settings


class RemoteApiError(RuntimeError):
    pass


def remote_api_configured() -> bool:
    return bool(settings.remote_api_url.strip())


class RemoteIngestClient:
    """Authenticated client for the remoteLessonsGPT ingest API."""

    def __init__(self, token: str, base_url: str | None = None):
        self.base_url = (base_url or settings.remote_api_url).rstrip("/")
        self.token = token.strip()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float = 120.0,
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(method, url, headers=self._headers(), json=json, params=params)
        except httpx.HTTPError as exc:
            raise RemoteApiError(f"Remote API unreachable at {self.base_url}: {exc}") from exc
        if response.status_code >= 400:
            detail = response.text.strip()
            try:
                payload = response.json()
                detail = payload.get("detail") if isinstance(payload, dict) else detail
            except Exception:
                pass
            raise RemoteApiError(f"Remote API {method} {path} failed ({response.status_code}): {detail}")
        if response.status_code == 204:
            return None
        if not response.content:
            return {}
        return response.json()

    @classmethod
    def login(cls, email: str, password: str, base_url: str | None = None) -> dict[str, Any]:
        url = (base_url or settings.remote_api_url).rstrip("/")
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{url}/api/v1/auth/login",
                    json={"email": email, "password": password},
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            raise RemoteApiError(f"Remote login failed: {exc}") from exc
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            raise RemoteApiError(str(detail))
        return response.json()

    def me(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/auth/me")

    def register_book(
        self,
        *,
        resource_id: str,
        subject_id: str | None,
        original_filename: str,
        size_bytes: int,
        sha256: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/ingest/books",
            json={
                "resource_id": resource_id,
                "subject_id": subject_id,
                "original_filename": original_filename,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "metadata": metadata,
            },
        )

    def create_job(
        self,
        *,
        job_id: str,
        book_resource_id: str,
        book_id: str | None,
        start_page: int,
        end_page: int | None,
        extractor_backend: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/ingest/jobs",
            json={
                "job_id": job_id,
                "book_resource_id": book_resource_id,
                "book_id": book_id,
                "start_page": start_page,
                "end_page": end_page,
                "extractor_backend": extractor_backend,
                "metadata": metadata or {},
            },
        )

    def ingest_page(
        self,
        job_id: str,
        *,
        book_id: str,
        book_resource_id: str,
        pdf_page_number: int,
        printed_page_number: str | None,
        page_json: dict[str, Any],
        documents: list[dict[str, Any]],
        progress: float | None = None,
        total_pages: int | None = None,
        stage: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/ingest/jobs/{job_id}/pages",
            json={
                "book_id": book_id,
                "book_resource_id": book_resource_id,
                "pdf_page_number": pdf_page_number,
                "printed_page_number": printed_page_number,
                "page_json": page_json,
                "documents": documents,
                "progress": progress,
                "total_pages": total_pages,
                "stage": stage,
                "message": message,
            },
            timeout=180.0,
        )

    def complete_job(
        self,
        job_id: str,
        *,
        book_id: str,
        extracted_records: int,
        indexed_records: int,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = dict(result or {})
        payload.setdefault("book_id", book_id)
        payload.setdefault("extracted_records", extracted_records)
        payload.setdefault("indexed_records", indexed_records)
        return self._request(
            "POST",
            f"/api/v1/ingest/jobs/{job_id}/complete",
            json={
                "book_id": book_id,
                "extracted_records": extracted_records,
                "indexed_records": indexed_records,
                "result": payload,
            },
        )

    def request_json(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        return self._request(method, path, json=json)

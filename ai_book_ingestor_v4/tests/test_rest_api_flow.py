import json

from fastapi.testclient import TestClient

import book_ingestor.api.app as api_app
from book_ingestor.api.job_store import JobStore


class DummyWorkers:
    def start(self):
        pass

    def stop(self):
        pass


def test_upload_create_track_cancel_job(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    books_root = data_root / "books"
    jobs_root = data_root / "jobs"
    books_root.mkdir(parents=True)
    jobs_root.mkdir(parents=True)
    monkeypatch.setattr(api_app, "store", JobStore(data_root / "jobs.sqlite3"))
    monkeypatch.setattr(api_app, "workers", DummyWorkers())
    monkeypatch.setattr(api_app, "BOOKS_ROOT", books_root)
    monkeypatch.setattr(api_app, "JOBS_ROOT", jobs_root)

    with TestClient(api_app.app) as client:
        response = client.post(
            "/api/v1/books",
            files={"file": ("كتاب.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
            data={"metadata": json.dumps({"country": "Jordan", "language": "ar"})},
        )
        assert response.status_code == 201
        resource_id = response.json()["resource_id"]

        response = client.post(
            f"/api/v1/books/{resource_id}/extraction-jobs",
            json={"start_page": 1, "resume": True, "index_to_opensearch": False},
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        assert response.json()["status"] == "queued"

        tracked = client.get(f"/api/v1/jobs/{job_id}")
        assert tracked.status_code == 200
        assert tracked.json()["stage"] == "queued"

        cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel")
        assert cancelled.status_code == 202
        assert cancelled.json()["status"] == "cancelled"

        events = client.get(f"/api/v1/jobs/{job_id}/events").json()["items"]
        assert [x["event_type"] for x in events] == ["queued", "cancelled"]

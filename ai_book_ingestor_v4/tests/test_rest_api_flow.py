import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

import book_ingestor.api.app as api_app
from book_ingestor.api.auth_utils import create_access_token
from book_ingestor.api.job_store import JobStore
from book_ingestor.config import settings


class DummyWorkers:
    def start(self):
        pass

    def stop(self):
        pass


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL", settings.database_url)
    try:
        test_store = JobStore(url)
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available: {exc}")

    data_root = tmp_path / "data"
    books_root = data_root / "books"
    jobs_root = data_root / "jobs"
    books_root.mkdir(parents=True)
    jobs_root.mkdir(parents=True)

    suffix = uuid.uuid4().hex[:8]
    country = test_store.create_country(name=f"Jordan-{suffix}", name_ar=f"الأردن-{suffix}", code=f"JO-{suffix}")
    system = test_store.create_education_system(country_id=country["id"], name=f"National-{suffix}", name_ar=f"الوطني-{suffix}")
    grade = test_store.create_grade(education_system_id=system["id"], name=f"Grade 8-{suffix}", name_ar=f"الصف الثامن-{suffix}", sort_order=8)
    subject = test_store.create_subject(grade_id=grade["id"], name=f"Science-{suffix}", name_ar=f"العلوم-{suffix}")

    admin = test_store.create_user(
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        password="AdminTest123!",
        full_name="Test Admin",
        role="admin",
    )
    token = create_access_token({"sub": admin["id"], "role": admin["role"], "email": admin["email"]})
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(api_app, "store", test_store)
    monkeypatch.setattr(api_app, "workers", DummyWorkers())
    monkeypatch.setattr(api_app, "BOOKS_ROOT", books_root)
    monkeypatch.setattr(api_app, "JOBS_ROOT", jobs_root)

    with TestClient(api_app.app) as client:
        yield client, headers, subject["id"], test_store
    test_store.close()


def test_upload_create_track_cancel_job(api_client):
    client, headers, subject_id, _store = api_client
    response = client.post(
        "/api/v1/books",
        headers=headers,
        files={"file": ("كتاب.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        data={"metadata": json.dumps({"language": "ar"}), "subject_id": subject_id},
    )
    assert response.status_code == 201
    resource_id = response.json()["resource_id"]
    assert response.json()["subject_id"] == subject_id

    response = client.post(
        f"/api/v1/books/{resource_id}/extraction-jobs",
        headers=headers,
        json={"start_page": 1, "resume": True, "index_to_opensearch": False},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert response.json()["status"] == "queued"

    tracked = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert tracked.status_code == 200
    assert tracked.json()["stage"] == "queued"

    cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers)
    assert cancelled.status_code == 202
    assert cancelled.json()["status"] == "paused"

    events = client.get(f"/api/v1/jobs/{job_id}/events", headers=headers).json()["items"]
    assert "queued" in [x["event_type"] for x in events]
    assert "paused" in [x["event_type"] for x in events]

    resumed = client.post(f"/api/v1/jobs/{job_id}/resume", headers=headers)
    assert resumed.status_code == 202
    assert resumed.json()["status"] == "queued"
    assert resumed.json()["job_id"] == job_id

    stopped = client.post(f"/api/v1/jobs/{job_id}/stop", headers=headers)
    assert stopped.status_code == 202
    assert stopped.json()["status"] == "paused"

    deleted = client.delete(f"/api/v1/jobs/{job_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(f"/api/v1/jobs/{job_id}", headers=headers).status_code == 404

    deleted = client.delete(f"/api/v1/books/{resource_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(f"/api/v1/books/{resource_id}", headers=headers).status_code == 404


def test_failed_job_exposes_error_and_traceback(api_client):
    client, headers, subject_id, store = api_client
    response = client.post(
        "/api/v1/books",
        headers=headers,
        files={"file": ("كتاب.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        data={"metadata": json.dumps({"language": "ar"}), "subject_id": subject_id},
    )
    assert response.status_code == 201
    resource_id = response.json()["resource_id"]

    created = client.post(
        f"/api/v1/books/{resource_id}/extraction-jobs",
        headers=headers,
        json={"start_page": 1, "resume": True, "index_to_opensearch": False},
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]

    store.fail_job(
        job_id,
        "Vision model returned an empty response (no JSON content)",
        "Traceback (most recent call last):\n  File worker.py",
    )

    detail = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
    assert detail["status"] == "failed"
    assert "empty response" in detail["error"]
    assert "Traceback" in (detail["traceback"] or "")

    errors = client.get(f"/api/v1/jobs/{job_id}/errors", headers=headers).json()["items"]
    assert errors
    assert errors[0]["source"] == "job"
    assert "empty response" in errors[0]["error"]

    events = client.get(f"/api/v1/jobs/{job_id}/events", headers=headers).json()["items"]
    failed = [item for item in events if item["event_type"] == "failed"]
    assert failed
    assert failed[-1]["message"]
    assert failed[-1]["payload"]["error"]


def test_student_cannot_login(api_client):
    client, _, _, store = api_client
    student = store.create_user(
        email=f"student-{uuid.uuid4().hex[:8]}@example.com",
        password="Student123!",
        full_name="Student",
        role="student",
    )
    response = client.post("/api/v1/auth/login", json={"email": student["email"], "password": "Student123!"})
    assert response.status_code == 403

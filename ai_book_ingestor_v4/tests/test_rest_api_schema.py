from book_ingestor.api.app import app


def test_rest_api_routes_are_exposed():
    schema = app.openapi()
    paths = schema["paths"]
    required = {
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/admin/users",
        "/api/v1/catalog/tree",
        "/api/v1/catalog/countries",
        "/api/v1/books",
        "/api/v1/books/{resource_id}",
        "/api/v1/books/{resource_id}/extraction-jobs",
        "/api/v1/jobs/{job_id}",
        "/api/v1/jobs/{job_id}/cancel",
        "/api/v1/jobs/{job_id}/stop",
        "/api/v1/jobs/{job_id}/resume",
        "/api/v1/jobs/{job_id}/retry",
        "/api/v1/jobs/{job_id}/events",
        "/api/v1/jobs/{job_id}/events/stream",
        "/api/v1/jobs/{job_id}/quality-report",
        "/api/v1/jobs/{job_id}/manifest",
        "/api/v1/jobs/{job_id}/errors",
        "/api/v1/search",
        "/api/v1/indexed-books/{book_id}/questions/search",
    }
    assert required.issubset(paths.keys())

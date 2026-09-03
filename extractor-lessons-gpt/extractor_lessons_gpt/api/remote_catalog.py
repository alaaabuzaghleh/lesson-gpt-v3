from __future__ import annotations

from typing import Any

from extractor_lessons_gpt.api.remote_client import RemoteIngestClient


def remote_catalog_metadata(client: RemoteIngestClient, subject_id: str) -> dict[str, Any]:
    tree_payload = client.request_json("GET", "/api/v1/catalog/tree")
    for country in tree_payload.get("items") or []:
        for system in country.get("education_systems") or []:
            for grade in system.get("grades") or []:
                for subject in grade.get("subjects") or []:
                    if str(subject.get("id")) != str(subject_id):
                        continue
                    return {
                        "country": country.get("name_ar") or country.get("name"),
                        "country_id": country.get("id"),
                        "country_code": country.get("code"),
                        "education_system": system.get("name_ar") or system.get("name"),
                        "education_system_id": system.get("id"),
                        "grade": grade.get("name_ar") or grade.get("name"),
                        "grade_id": grade.get("id"),
                        "subject": subject.get("name_ar") or subject.get("name"),
                        "subject_id": subject.get("id"),
                    }
    raise ValueError(f"Subject {subject_id} not found in remote catalog")

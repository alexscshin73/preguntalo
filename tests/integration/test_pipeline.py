import uuid


EXAMPLE_MANUAL = """# 개요
페이지 1
이 문서는 한국어로 된 개요를 포함합니다.
![로그인 화면](login.png)

\f
Página 2
## DETAILS
This section mentions multi-lingual support and includes English text.

\f
Página 3
SECCIÓN
Aquí hablamos de español y procedimientos.
"""


def create_manual(client):
    manual_code = f"multi-lingual-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/manuals",
        json={
            "title": "통합 매뉴얼",
            "manualCode": manual_code,
            "category": "test",
            "defaultLanguage": "ko",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def upload_manual(client, manual_id: str):
    response = client.post(
        f"/api/v1/manuals/{manual_id}/upload",
        data={"version_label": "v1.0", "source_language": "ko"},
        files={"file": ("sample.md", EXAMPLE_MANUAL.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 201
    return response.json()


def test_upload_to_search_pipeline(client, ingestion_worker):
    manual_id = create_manual(client)
    upload_payload = upload_manual(client, manual_id)

    assert upload_payload["status"] == "queued"
    assert upload_payload["pageCount"] == 0

    job = ingestion_worker.process(job_id=upload_payload["ingestionJobId"])
    assert job is not None and job.status == "completed"

    search_response = client.post(
        "/api/v1/search",
        json={"query": "로그인 화면", "language": "ko", "manualIds": [manual_id], "topK": 5},
    )
    assert search_response.status_code == 200

    results = search_response.json().get("results", [])
    assert results and results[0]["manualId"] == manual_id

    page_response = client.get(
        f"/api/v1/manuals/{manual_id}/versions/{upload_payload['versionId']}/pages/2"
    )
    assert page_response.status_code == 200
    assert page_response.json()["totalPages"] == 3


def test_download_preview_and_reindex_flow(client, ingestion_worker):
    manual_id = create_manual(client)
    upload_payload = upload_manual(client, manual_id)
    version_id = upload_payload["versionId"]

    download_response = client.get(f"/api/v1/manuals/{manual_id}/versions/{version_id}/download")
    assert download_response.status_code == 200
    assert b"DETAILS" in download_response.content

    preview_response = client.get(f"/api/v1/manuals/{manual_id}/versions/{version_id}/preview")
    assert preview_response.status_code == 200
    assert preview_response.json()["totalPages"] == 3

    initial_job = ingestion_worker.process(job_id=upload_payload["ingestionJobId"])
    assert initial_job is not None and initial_job.status == "completed"

    reindex_response = client.post(f"/api/v1/manuals/{manual_id}/versions/{version_id}/reindex")
    assert reindex_response.status_code == 201

    reindex_payload = reindex_response.json()
    assert reindex_payload["status"] == "queued"
    assert reindex_payload["ingestionJobId"] != upload_payload["ingestionJobId"]

    reindexed_job = ingestion_worker.process(job_id=reindex_payload["ingestionJobId"])
    assert reindexed_job is not None and reindexed_job.status == "completed"

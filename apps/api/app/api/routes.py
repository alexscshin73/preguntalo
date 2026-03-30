from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.manuals import (
    ManualCreateRequest,
    ManualCreateResponse,
    ManualDeleteResponse,
    ManualListResponse,
    ManualReindexResponse,
    ManualTagUpdateRequest,
    ManualTagUpdateResponse,
    ManualUpdateRequest,
    ManualUpdateResponse,
    ManualUploadResponse,
    ManualVersionDeleteResponse,
    ManualVersionListResponse,
    ManualVersionUpdateRequest,
    ManualVersionUpdateResponse,
    PopularTagListResponse,
)
from app.schemas.search import (
    AnswerRequest,
    AnswerResponse,
    PopularQueryTagResponse,
    SearchRequest,
    SearchResponse,
    SectionDetailResponse,
    ViewerPageResponse,
)
from app.services.answer import AnswerService
from app.services.manuals import ManualService
from app.services.search import SearchService


router = APIRouter()
search_service = SearchService()
answer_service = AnswerService()
manual_service = ManualService()


def _inline_content_disposition(filename: str) -> str:
    ascii_filename = "".join(char if ord(char) < 128 and char not in {'"', "\\"} else "_" for char in filename).strip()
    if not ascii_filename:
        ascii_filename = "download.bin"
    return f"inline; filename=\"{ascii_filename}\"; filename*=UTF-8''{quote(filename)}"


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/manuals", response_model=ManualListResponse)
def list_manuals(db: Session = Depends(get_db)) -> ManualListResponse:
    return manual_service.list_manuals(db)


@router.post("/manuals", response_model=ManualCreateResponse, status_code=status.HTTP_201_CREATED)
def create_manual(payload: ManualCreateRequest, db: Session = Depends(get_db)) -> ManualCreateResponse:
    return manual_service.create_manual(db, payload)


@router.put("/manuals/{manual_id}", response_model=ManualUpdateResponse)
def update_manual(
    manual_id: str,
    payload: ManualUpdateRequest,
    db: Session = Depends(get_db),
) -> ManualUpdateResponse:
    return manual_service.update_manual(db, manual_id, payload)


@router.delete("/manuals/{manual_id}", response_model=ManualDeleteResponse)
def delete_manual(manual_id: str, db: Session = Depends(get_db)) -> ManualDeleteResponse:
    return manual_service.delete_manual(db, manual_id)


@router.put("/manuals/{manual_id}/tags", response_model=ManualTagUpdateResponse)
def update_manual_tags(
    manual_id: str,
    payload: ManualTagUpdateRequest,
    db: Session = Depends(get_db),
) -> ManualTagUpdateResponse:
    return manual_service.update_tags(db, manual_id, payload.tags)


@router.get("/manuals/{manual_id}/versions", response_model=ManualVersionListResponse)
def list_manual_versions(manual_id: str, db: Session = Depends(get_db)) -> ManualVersionListResponse:
    return manual_service.list_versions(db, manual_id)


@router.put(
    "/manuals/{manual_id}/versions/{version_id}",
    response_model=ManualVersionUpdateResponse,
)
def update_manual_version(
    manual_id: str,
    version_id: str,
    payload: ManualVersionUpdateRequest,
    db: Session = Depends(get_db),
) -> ManualVersionUpdateResponse:
    return manual_service.update_manual_version(db, manual_id, version_id, payload)


@router.delete(
    "/manuals/{manual_id}/versions/{version_id}",
    response_model=ManualVersionDeleteResponse,
)
def delete_manual_version(
    manual_id: str,
    version_id: str,
    db: Session = Depends(get_db),
) -> ManualVersionDeleteResponse:
    return manual_service.delete_manual_version(db, manual_id, version_id)


@router.post("/manuals/{manual_id}/upload", response_model=ManualUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_manual_version(
    manual_id: str,
    version_label: str = Form(...),
    source_language: str = Form("en"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ManualUploadResponse:
    return await manual_service.upload_manual(
        db=db,
        manual_id=manual_id,
        version_label=version_label,
        source_language=source_language,
        file=file,
    )


@router.post(
    "/manuals/{manual_id}/versions/{version_id}/reindex",
    response_model=ManualReindexResponse,
    status_code=status.HTTP_201_CREATED,
)
def reindex_manual_version(manual_id: str, version_id: str, db: Session = Depends(get_db)) -> ManualReindexResponse:
    return manual_service.reindex_manual_version(db, manual_id, version_id)


@router.post(
    "/manuals/{manual_id}/versions/{version_id}/replace",
    response_model=ManualVersionUpdateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def replace_manual_version(
    manual_id: str,
    version_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ManualVersionUpdateResponse:
    return await manual_service.replace_manual_version(db, manual_id, version_id, file)


@router.get(
    "/manuals/{manual_id}/versions/{version_id}/download",
)
def download_manual_version(
    manual_id: str,
    version_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    asset, content = manual_service.download_version_source_file(db, manual_id, version_id)
    headers = {"Content-Disposition": _inline_content_disposition(asset.original_filename)}
    return StreamingResponse(
        BytesIO(content),
        media_type=asset.mime_type or "application/octet-stream",
        headers=headers,
    )


@router.get("/manuals/{manual_id}/versions/{version_id}/preview")
def get_manual_version_preview(
    manual_id: str,
    version_id: str,
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    return manual_service.get_version_preview_metadata(db, manual_id, version_id)


@router.get("/tags/popular", response_model=PopularTagListResponse)
def popular_tags(db: Session = Depends(get_db)) -> PopularTagListResponse:
    return manual_service.popular_tags(db)


@router.post("/search", response_model=SearchResponse)
def search_manuals(payload: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    return search_service.search(db, payload)


@router.post("/answer", response_model=AnswerResponse)
def answer_manuals(payload: AnswerRequest, db: Session = Depends(get_db)) -> AnswerResponse:
    return answer_service.answer(db, payload)


@router.get("/search/tags/popular", response_model=PopularQueryTagResponse)
def popular_query_tags(limit: int = 8, db: Session = Depends(get_db)) -> PopularQueryTagResponse:
    return search_service.popular_query_tags(db, limit=limit)


@router.get("/sections/{section_id}", response_model=SectionDetailResponse)
def get_section_detail(section_id: str, language: str = "en", db: Session = Depends(get_db)) -> SectionDetailResponse:
    detail = search_service.get_section_detail(db, section_id=section_id, language=language)
    if detail is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return detail


@router.get(
    "/manuals/{manual_id}/versions/{version_id}/pages/{page_number}",
    response_model=ViewerPageResponse,
)
def get_viewer_page(
    manual_id: str,
    version_id: str,
    page_number: int,
    section_id: str | None = None,
    db: Session = Depends(get_db),
) -> ViewerPageResponse:
    detail = search_service.get_viewer_page(
        db,
        manual_id=manual_id,
        version_id=version_id,
        page_number=page_number,
        section_id=section_id,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Viewer page not found")
    return detail

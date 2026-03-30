import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import sha256_hexdigest, slugify
from app.models.file_asset import FileAsset
from app.models.manual import Manual
from app.models.manual_version import ManualVersion
from app.models.search_result_cache import SearchResultCache
from app.schemas.manuals import (
    ManualCreateRequest,
    ManualCreateResponse,
    ManualDeleteResponse,
    ManualListItem,
    ManualListResponse,
    ManualReindexResponse,
    ManualTagUpdateResponse,
    ManualUpdateRequest,
    ManualUpdateResponse,
    ManualUploadResponse,
    ManualVersionDeleteResponse,
    ManualVersionItem,
    ManualVersionListResponse,
    ManualVersionUpdateRequest,
    ManualVersionUpdateResponse,
    PopularTagItem,
    PopularTagListResponse,
)
from app.services.ingestion import IngestionService
from app.services.parser import DocumentParser
from app.services.storage import StorageService
from app.services.tags import TagService


class ManualService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.storage_service = StorageService()
        self.ingestion_service = IngestionService()
        self.parser = DocumentParser()
        self.tag_service = TagService()

    def list_manuals(self, db: Session) -> ManualListResponse:
        manuals = db.scalars(select(Manual).order_by(Manual.created_at.desc())).all()
        items = [
            ManualListItem(
                id=manual.id,
                title=manual.title,
                category=manual.category,
                tags=self.tag_service.load_tags(manual.tags_json),
                default_language=manual.default_language,
                latest_version=manual.versions[-1].version_label if manual.versions else "-",
                updatedAt=manual.updated_at,
            )
            for manual in manuals
        ]
        return ManualListResponse(items=items)

    def create_manual(self, db: Session, payload: ManualCreateRequest) -> ManualCreateResponse:
        existing = db.scalar(select(Manual).where(Manual.manual_code == payload.manual_code))
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Manual code already exists")

        manual_id = f"man_{slugify(payload.manual_code)}"
        conflicting_id = db.get(Manual, manual_id)
        if conflicting_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Manual code resolves to an existing manual identifier",
            )

        manual = Manual(
            id=manual_id,
            title=payload.title,
            manual_code=payload.manual_code,
            category=payload.category,
            tags_json=self.tag_service.dump_tags(
                self.tag_service.merge_tags(
                    payload.tags,
                    self.tag_service.extract_tags(payload.title, payload.category, payload.manual_code),
                )
            ),
            default_language=payload.default_language,
            status="draft",
        )
        db.add(manual)
        db.commit()
        db.refresh(manual)

        return ManualCreateResponse(
            id=manual.id,
            title=manual.title,
            manualCode=manual.manual_code,
            category=manual.category,
            tags=self.tag_service.load_tags(manual.tags_json),
            defaultLanguage=manual.default_language,
            status=manual.status,
        )

    def update_manual(self, db: Session, manual_id: str, payload: ManualUpdateRequest) -> ManualUpdateResponse:
        manual = self._get_manual(db, manual_id)
        manual.title = payload.title.strip()
        db.commit()
        db.refresh(manual)
        return ManualUpdateResponse(
            id=manual.id,
            title=manual.title,
            manualCode=manual.manual_code,
            category=manual.category,
            tags=self.tag_service.load_tags(manual.tags_json),
            defaultLanguage=manual.default_language,
            status=manual.status,
        )

    def delete_manual(self, db: Session, manual_id: str) -> ManualDeleteResponse:
        manual = self._get_manual(db, manual_id)
        db.delete(manual)
        db.commit()
        return ManualDeleteResponse(id=manual_id, deleted=True)

    def list_versions(self, db: Session, manual_id: str) -> ManualVersionListResponse:
        manual = self._get_manual(db, manual_id)
        items = [ManualVersionItem(**self._serialize_version(version)) for version in manual.versions]
        return ManualVersionListResponse(items=items)

    async def upload_manual(
        self,
        db: Session,
        manual_id: str,
        version_label: str,
        source_language: str,
        file: UploadFile,
    ) -> ManualUploadResponse:
        manual = self._get_manual(db, manual_id)
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
        self._validate_supported_file(file.filename or "")

        file_asset = FileAsset(
            id=f"asset_{uuid.uuid4().hex[:16]}",
            storage_provider=self.settings.storage_backend.lower(),
            bucket=self.settings.s3_bucket,
            object_key=self._object_key(manual.manual_code, version_label, file.filename or "upload.bin"),
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=len(content),
            sha256=sha256_hexdigest(content),
            original_filename=file.filename or "upload.bin",
        )

        try:
            self.storage_service.upload_bytes(
                content=content,
                object_key=file_asset.object_key,
                content_type=file_asset.mime_type,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to persist file asset: {exc}",
            ) from exc

        version = ManualVersion(
            id=f"ver_{uuid.uuid4().hex[:16]}",
            manual_id=manual.id,
            source_file_asset_id=file_asset.id,
            version_label=version_label,
            source_language=source_language,
            tags_json=self.tag_service.dump_tags([]),
            status="uploaded",
        )

        db.add(file_asset)
        db.add(version)
        db.flush()

        job = self.ingestion_service.enqueue_manual_version(db, version.id)
        manual.status = "processing"
        db.commit()

        return ManualUploadResponse(
            manualId=manual.id,
            versionId=version.id,
            ingestionJobId=job.id,
            fileAssetId=file_asset.id,
            status=job.status,
            detail=job.detail or "",
            pageCount=0,
            sectionCount=0,
            chunkCount=0,
        )

    def reindex_manual_version(self, db: Session, manual_id: str, version_id: str) -> ManualReindexResponse:
        manual = self._get_manual(db, manual_id)
        version = self._get_manual_version(db, manual_id, version_id)
        if version.source_file_asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source file asset is missing for the specified version",
            )

        version.status = "uploaded"
        version.tags_json = self.tag_service.dump_tags([])
        job = self.ingestion_service.enqueue_manual_version(db, version.id)
        manual.status = "processing"
        job.status = "processing"
        job.detail = "Selected manual is being transformed into searchable knowledge."
        db.commit()

        try:
            content = self.storage_service.download_bytes(version.source_file_asset.object_key)
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.detail = f"Failed to download source file: {exc}"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to download source file: {exc}",
            ) from exc

        page_count, section_count, chunk_count = self.ingestion_service.process_manual_version(
            db=db,
            version=version,
            job=job,
            filename=version.source_file_asset.original_filename,
            content=content,
        )
        db.commit()
        return ManualReindexResponse(
            manualId=manual.id,
            versionId=version.id,
            ingestionJobId=job.id,
            status=job.status,
            detail=job.detail or "",
            pageCount=page_count,
            sectionCount=section_count,
            chunkCount=chunk_count,
            tags=self.tag_service.load_tags(version.tags_json),
        )

    async def replace_manual_version(
        self,
        db: Session,
        manual_id: str,
        version_id: str,
        file: UploadFile,
    ) -> ManualVersionUpdateResponse:
        manual = self._get_manual(db, manual_id)
        version = self._get_manual_version(db, manual_id, version_id)
        asset = version.source_file_asset
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source file asset is missing for the specified version",
            )

        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

        requested_filename = file.filename or asset.original_filename
        original_filename = self._normalize_filename(
            current_filename=asset.original_filename,
            requested_filename=requested_filename,
        )
        next_version_label = self._version_label_from_filename(original_filename)
        next_object_key = self._object_key(manual.manual_code, next_version_label, original_filename)

        try:
            self.storage_service.upload_bytes(
                content=content,
                object_key=next_object_key,
                content_type=file.content_type or asset.mime_type or "application/octet-stream",
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to replace source file: {exc}",
            ) from exc

        previous_object_key = asset.object_key
        asset.object_key = next_object_key
        asset.mime_type = file.content_type or asset.mime_type or "application/octet-stream"
        asset.size_bytes = len(content)
        asset.sha256 = sha256_hexdigest(content)
        asset.original_filename = original_filename

        version.version_label = next_version_label
        version.status = "uploaded"
        version.indexed_at = None
        version.tags_json = self.tag_service.dump_tags([])

        job = self.ingestion_service.enqueue_manual_version(db, version.id)
        manual.status = "processing"
        db.commit()
        db.refresh(version)

        if previous_object_key != next_object_key:
            try:
                self.storage_service.delete_bytes(previous_object_key)
            except Exception:
                pass

        return ManualVersionUpdateResponse(**self._serialize_version(version, ingestion_job_id=job.id))

    def update_manual_version(
        self,
        db: Session,
        manual_id: str,
        version_id: str,
        payload: ManualVersionUpdateRequest,
    ) -> ManualVersionUpdateResponse:
        version = self._get_manual_version(db, manual_id, version_id)
        original_filename = self._normalize_filename(
            current_filename=version.source_file_asset.original_filename,
            requested_filename=payload.original_filename,
        )
        version.source_file_asset.original_filename = original_filename
        version.version_label = self._version_label_from_filename(original_filename)
        version.tags_json = self.tag_service.dump_tags(payload.tags)
        db.commit()
        db.refresh(version)

        return ManualVersionUpdateResponse(**self._serialize_version(version))

    def update_tags(self, db: Session, manual_id: str, tags: list[str]) -> ManualTagUpdateResponse:
        manual = self._get_manual(db, manual_id)
        manual.tags_json = self.tag_service.dump_tags(tags)
        db.commit()
        return ManualTagUpdateResponse(manualId=manual.id, tags=self.tag_service.load_tags(manual.tags_json))

    def delete_manual_version(
        self,
        db: Session,
        manual_id: str,
        version_id: str,
    ) -> ManualVersionDeleteResponse:
        manual = self._get_manual(db, manual_id)
        version = self._get_manual_version(db, manual_id, version_id)
        asset = version.source_file_asset

        should_delete_asset = False
        if asset is not None:
            remaining_asset_versions = db.scalar(
                select(func.count())
                .select_from(ManualVersion)
                .where(
                    ManualVersion.source_file_asset_id == asset.id,
                    ManualVersion.id != version.id,
                )
            ) or 0
            should_delete_asset = remaining_asset_versions == 0

        if should_delete_asset and asset is not None:
            try:
                self.storage_service.delete_bytes(asset.object_key)
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to delete source file: {exc}",
                ) from exc

        db.delete(version)
        db.execute(delete(SearchResultCache))

        if should_delete_asset and asset is not None:
            db.delete(asset)

        remaining_manual_versions = db.scalar(
            select(func.count())
            .select_from(ManualVersion)
            .where(
                ManualVersion.manual_id == manual.id,
                ManualVersion.id != version.id,
            )
        ) or 0
        if remaining_manual_versions == 0:
            manual.status = "draft"

        db.commit()
        return ManualVersionDeleteResponse(id=version_id, manualId=manual.id, deleted=True)

    def popular_tags(self, db: Session, limit: int = 12) -> PopularTagListResponse:
        manuals = db.scalars(select(Manual).order_by(Manual.created_at.desc())).all()
        tag_counts: dict[str, int] = {}

        for manual in manuals:
            for tag in self.tag_service.load_tags(manual.tags_json):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

            if manual.versions:
                latest_version = manual.versions[-1]
                for tag in self.tag_service.load_tags(latest_version.tags_json):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                for section in latest_version.sections:
                    for tag in self.tag_service.load_tags(section.tags_json):
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1

        ranked = sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
        return PopularTagListResponse(items=[PopularTagItem(tag=tag, count=count) for tag, count in ranked])

    def _get_manual(self, db: Session, manual_id: str) -> Manual:
        manual = db.get(Manual, manual_id)
        if manual is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manual not found")
        return manual

    def _get_manual_version(self, db: Session, manual_id: str, version_id: str) -> ManualVersion:
        version = db.get(ManualVersion, version_id)
        if version is None or version.manual_id != manual_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manual version not found for the requested manual",
            )
        return version

    def _object_key(self, manual_code: str, version_label: str, filename: str) -> str:
        safe_filename = slugify(filename.rsplit(".", 1)[0])
        extension = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        return f"manuals/{slugify(manual_code)}/{slugify(version_label)}/{safe_filename}.{extension.lower()}"

    def get_version_source_asset(self, db: Session, manual_id: str, version_id: str) -> tuple[ManualVersion, FileAsset]:
        version = self._get_manual_version(db, manual_id, version_id)
        asset = version.source_file_asset
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source file asset is missing for the specified version",
            )
        return version, asset

    def download_version_source_file(self, db: Session, manual_id: str, version_id: str) -> tuple[FileAsset, bytes]:
        _, asset = self.get_version_source_asset(db, manual_id, version_id)
        try:
            content = self.storage_service.download_bytes(asset.object_key)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch source file: {exc}",
            ) from exc
        return asset, content

    def get_version_preview_metadata(self, db: Session, manual_id: str, version_id: str) -> dict[str, int | str]:
        version, asset = self.get_version_source_asset(db, manual_id, version_id)
        try:
            content = self.storage_service.download_bytes(asset.object_key)
            parsed = self.parser.parse(asset.original_filename, content)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to inspect preview file: {exc}",
            ) from exc

        total_pages = max((page.page_number for page in parsed.pages), default=1)
        return {
            "manualId": version.manual_id,
            "versionId": version.id,
            "status": version.status,
            "mimeType": asset.mime_type or "application/octet-stream",
            "totalPages": total_pages,
        }

    def _validate_supported_file(self, filename: str) -> None:
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension in self.parser.supported_extensions():
            return

        supported = ", ".join(sorted(self.parser.supported_extensions()))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: .{extension or 'unknown'}. Supported types: {supported}",
        )

    def _normalize_filename(self, current_filename: str, requested_filename: str) -> str:
        normalized = requested_filename.strip()
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename cannot be empty")

        if "." not in normalized and "." in current_filename:
            extension = current_filename.rsplit(".", 1)[-1]
            normalized = f"{normalized}.{extension}"

        self._validate_supported_file(normalized)
        return normalized

    def _version_label_from_filename(self, filename: str) -> str:
        return filename.rsplit(".", 1)[0] if "." in filename else filename

    def _serialize_version(
        self,
        version: ManualVersion,
        *,
        ingestion_job_id: str | None = None,
    ) -> dict[str, object]:
        latest_job = version.ingestion_jobs[-1] if version.ingestion_jobs else None
        asset = version.source_file_asset
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source file asset is missing for the specified version",
            )

        has_indexed_tags = bool(version.indexed_at) or version.status == "indexed" or (
            latest_job is not None and latest_job.status == "completed"
        )

        return {
            "id": version.id,
            "manualId": version.manual_id,
            "versionLabel": version.version_label,
            "sourceLanguage": version.source_language,
            "originalFilename": asset.original_filename,
            "sizeBytes": asset.size_bytes,
            "uploadedAt": version.created_at,
            "status": version.status,
            "ingestionJobId": ingestion_job_id or (latest_job.id if latest_job else ""),
            "indexedAt": version.indexed_at,
            "latestJobStatus": latest_job.status if latest_job else None,
            "latestJobDetail": latest_job.detail if latest_job else None,
            "latestJobUpdatedAt": latest_job.updated_at if latest_job else None,
            "tags": self.tag_service.load_tags(version.tags_json) if has_indexed_tags else [],
        }

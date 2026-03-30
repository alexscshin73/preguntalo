import uuid
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import sha256_hexdigest, slugify
from app.db import SessionLocal
from app.models.file_asset import FileAsset
from app.models.manual import Manual
from app.models.manual_version import ManualVersion
from app.services.ingestion import IngestionService
from app.services.storage import StorageService


DEFAULT_MANUAL_ID = "man_citygolf"
DEFAULT_MANUAL_CODE = "citygolf"
DEFAULT_VERSION_LABEL = "README"
DEFAULT_FILENAME = "README.md"
logger = logging.getLogger(__name__)
DEFAULT_CONTENT = """# Citygolf Manual

preguntalo 기본 매뉴얼입니다.

## 사용 방법
1. 매뉴얼 파일을 업로드합니다.
2. 업로드된 파일은 ingestion job으로 등록됩니다.
3. worker가 문서를 파싱하고 임베딩을 생성합니다.
4. 검색 결과에서 관련 페이지와 원문 미리보기를 확인할 수 있습니다.

## Uso
1. Cargue un archivo manual.
2. El archivo se registra como un ingestion job.
3. El worker procesa el documento y genera embeddings.
4. Puede revisar resultados de busqueda y la vista previa del original.
"""


def ensure_default_manual_seed() -> None:
    settings = get_settings()
    storage_service = StorageService()
    ingestion_service = IngestionService()

    with SessionLocal() as db:
        manual = db.get(Manual, DEFAULT_MANUAL_ID)
        if manual is None:
            logger.info("Default manual seed missing. Creating manual '%s'.", DEFAULT_MANUAL_ID)
            manual = Manual(
                id=DEFAULT_MANUAL_ID,
                title="Citygolf",
                manual_code=DEFAULT_MANUAL_CODE,
                category="general",
                tags_json="[]",
                default_language="ko",
                status="processing",
            )
            db.add(manual)
            db.flush()
        else:
            logger.info("Default manual already exists: %s", manual.id)

        existing_version = db.scalar(
            select(ManualVersion)
            .join(FileAsset, ManualVersion.source_file_asset_id == FileAsset.id)
            .where(ManualVersion.manual_id == manual.id, FileAsset.original_filename == DEFAULT_FILENAME)
        )
        if existing_version is not None:
            logger.info("Default README already exists for manual %s: %s", manual.id, existing_version.id)
            if manual.status == "draft":
                manual.status = "processing"
                db.commit()
            return

        content = DEFAULT_CONTENT.encode("utf-8")
        object_key = f"manuals/{slugify(DEFAULT_MANUAL_CODE)}/{slugify(DEFAULT_VERSION_LABEL)}/readme.md"
        logger.info("Uploading default README asset to %s", object_key)
        storage_service.upload_bytes(content=content, object_key=object_key, content_type="text/markdown")

        asset = FileAsset(
            id=f"asset_{uuid.uuid4().hex[:16]}",
            storage_provider=settings.storage_backend.lower(),
            bucket=settings.s3_bucket,
            object_key=object_key,
            mime_type="text/markdown",
            size_bytes=len(content),
            sha256=sha256_hexdigest(content),
            original_filename=DEFAULT_FILENAME,
        )
        version = ManualVersion(
            id=f"ver_{uuid.uuid4().hex[:16]}",
            manual_id=manual.id,
            source_file_asset_id=asset.id,
            version_label=DEFAULT_VERSION_LABEL,
            source_language="ko",
            status="uploaded",
        )

        db.add(asset)
        db.add(version)
        db.flush()
        ingestion_service.enqueue_manual_version(db, version.id)
        manual.status = "processing"
        db.commit()
        logger.info("Default manual seed created: manual=%s version=%s", manual.id, version.id)

from datetime import datetime

from pydantic import BaseModel, Field


class ManualListItem(BaseModel):
    id: str
    title: str
    category: str
    tags: list[str] = Field(default_factory=list)
    default_language: str
    latest_version: str
    updated_at: datetime = Field(alias="updatedAt")


class ManualListResponse(BaseModel):
    items: list[ManualListItem]


class ManualCreateRequest(BaseModel):
    title: str = Field(min_length=2)
    manual_code: str = Field(min_length=2, alias="manualCode")
    category: str = Field(default="general")
    tags: list[str] = Field(default_factory=list)
    default_language: str = Field(default="en", alias="defaultLanguage")


class ManualCreateResponse(BaseModel):
    id: str
    title: str
    manual_code: str = Field(alias="manualCode")
    category: str
    tags: list[str] = Field(default_factory=list)
    default_language: str = Field(alias="defaultLanguage")
    status: str


class ManualUpdateRequest(BaseModel):
    title: str = Field(min_length=2)


class ManualUpdateResponse(BaseModel):
    id: str
    title: str
    manual_code: str = Field(alias="manualCode")
    category: str
    tags: list[str] = Field(default_factory=list)
    default_language: str = Field(alias="defaultLanguage")
    status: str


class ManualDeleteResponse(BaseModel):
    id: str
    deleted: bool


class ManualVersionItem(BaseModel):
    id: str
    manual_id: str = Field(alias="manualId")
    version_label: str = Field(alias="versionLabel")
    source_language: str = Field(alias="sourceLanguage")
    original_filename: str = Field(alias="originalFilename")
    size_bytes: int = Field(alias="sizeBytes")
    uploaded_at: datetime = Field(alias="uploadedAt")
    status: str
    ingestion_job_id: str = Field(alias="ingestionJobId")
    indexed_at: datetime | None = Field(default=None, alias="indexedAt")
    latest_job_status: str | None = Field(default=None, alias="latestJobStatus")
    latest_job_detail: str | None = Field(default=None, alias="latestJobDetail")
    latest_job_updated_at: datetime | None = Field(default=None, alias="latestJobUpdatedAt")
    tags: list[str] = Field(default_factory=list)


class ManualTagUpdateRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)


class ManualTagUpdateResponse(BaseModel):
    manual_id: str = Field(alias="manualId")
    tags: list[str]


class PopularTagItem(BaseModel):
    tag: str
    count: int


class PopularTagListResponse(BaseModel):
    items: list[PopularTagItem]


class ManualVersionListResponse(BaseModel):
    items: list[ManualVersionItem]


class ManualUploadResponse(BaseModel):
    manual_id: str = Field(alias="manualId")
    version_id: str = Field(alias="versionId")
    ingestion_job_id: str = Field(alias="ingestionJobId")
    file_asset_id: str = Field(alias="fileAssetId")
    status: str
    detail: str
    page_count: int = Field(alias="pageCount")
    section_count: int = Field(alias="sectionCount")
    chunk_count: int = Field(alias="chunkCount")


class ManualReindexResponse(BaseModel):
    manual_id: str = Field(alias="manualId")
    version_id: str = Field(alias="versionId")
    ingestion_job_id: str = Field(alias="ingestionJobId")
    status: str
    detail: str
    page_count: int = Field(alias="pageCount")
    section_count: int = Field(alias="sectionCount")
    chunk_count: int = Field(alias="chunkCount")
    tags: list[str] = Field(default_factory=list)


class ManualVersionUpdateRequest(BaseModel):
    original_filename: str = Field(min_length=2, alias="originalFilename")
    tags: list[str] = Field(default_factory=list)


class ManualVersionUpdateResponse(BaseModel):
    id: str
    manual_id: str = Field(alias="manualId")
    version_label: str = Field(alias="versionLabel")
    source_language: str = Field(alias="sourceLanguage")
    original_filename: str = Field(alias="originalFilename")
    size_bytes: int = Field(alias="sizeBytes")
    uploaded_at: datetime = Field(alias="uploadedAt")
    status: str
    ingestion_job_id: str = Field(alias="ingestionJobId")
    indexed_at: datetime | None = Field(default=None, alias="indexedAt")
    latest_job_status: str | None = Field(default=None, alias="latestJobStatus")
    latest_job_detail: str | None = Field(default=None, alias="latestJobDetail")
    latest_job_updated_at: datetime | None = Field(default=None, alias="latestJobUpdatedAt")
    tags: list[str] = Field(default_factory=list)


class ManualVersionDeleteResponse(BaseModel):
    id: str
    manual_id: str = Field(alias="manualId")
    deleted: bool

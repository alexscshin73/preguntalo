from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=2)
    language: str = Field(default="en")
    tags: list[str] = Field(default_factory=list)
    manual_ids: list[str] = Field(default_factory=list, alias="manualIds")
    top_k: int = Field(default=10, ge=1, le=20, alias="topK")


class SearchResultItem(BaseModel):
    section_id: str = Field(alias="sectionId")
    manual_id: str = Field(alias="manualId")
    manual_title: str = Field(alias="manualTitle")
    version_id: str = Field(alias="versionId")
    version_label: str = Field(alias="versionLabel")
    heading: str
    snippet: str
    score: float
    page_start: int = Field(alias="pageStart")
    page_end: int = Field(alias="pageEnd")
    detail_url: str = Field(alias="detailUrl")
    tags: list[str] = Field(default_factory=list)


class AnswerCitationItem(BaseModel):
    section_id: str = Field(alias="sectionId")
    manual_id: str = Field(alias="manualId")
    manual_title: str = Field(alias="manualTitle")
    version_id: str = Field(alias="versionId")
    version_label: str = Field(alias="versionLabel")
    heading: str
    page_start: int = Field(alias="pageStart")
    page_end: int = Field(alias="pageEnd")
    detail_url: str = Field(alias="detailUrl")


class SearchResponse(BaseModel):
    query_language: str = Field(alias="queryLanguage")
    query_tags: list[str] = Field(default_factory=list, alias="queryTags")
    results: list[SearchResultItem]


class AnswerRequest(BaseModel):
    query: str = Field(min_length=2)
    language: str = Field(default="en")
    tags: list[str] = Field(default_factory=list)
    manual_ids: list[str] = Field(default_factory=list, alias="manualIds")
    top_k: int = Field(default=5, ge=1, le=20, alias="topK")


class AnswerResponse(BaseModel):
    query_language: str = Field(alias="queryLanguage")
    query_tags: list[str] = Field(default_factory=list, alias="queryTags")
    answer: str
    answer_source: str = Field(alias="answerSource")
    citations: list[AnswerCitationItem] = Field(default_factory=list)
    results: list[SearchResultItem]


class PopularQueryTagItem(BaseModel):
    tag: str
    query_count: int = Field(alias="queryCount")


class PopularQueryTagResponse(BaseModel):
    items: list[PopularQueryTagItem]


class CitationItem(BaseModel):
    page: int
    label: str
    viewer_url: str = Field(alias="viewerUrl")


class RelatedImageItem(BaseModel):
    image_id: str = Field(alias="imageId")
    thumbnail_url: str = Field(alias="thumbnailUrl")
    viewer_url: str = Field(alias="viewerUrl")


class SectionDetailResponse(BaseModel):
    section_id: str = Field(alias="sectionId")
    summary_language: str = Field(alias="summaryLanguage")
    summary: str
    tags: list[str] = Field(default_factory=list)
    citations: list[CitationItem]
    related_images: list[RelatedImageItem] = Field(alias="relatedImages")


class ViewerPageResponse(BaseModel):
    manual_id: str = Field(alias="manualId")
    manual_title: str = Field(alias="manualTitle")
    version_id: str = Field(alias="versionId")
    version_label: str = Field(alias="versionLabel")
    page_number: int = Field(alias="pageNumber")
    total_pages: int = Field(alias="totalPages")
    extracted_text: str = Field(alias="extractedText")
    section_id: str | None = Field(default=None, alias="sectionId")
    section_heading: str | None = Field(default=None, alias="sectionHeading")

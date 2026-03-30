from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ManualVersion(Base):
    __tablename__ = "manual_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    manual_id: Mapped[str] = mapped_column(ForeignKey("manuals.id", ondelete="CASCADE"), nullable=False, index=True)
    source_file_asset_id: Mapped[str] = mapped_column(ForeignKey("file_assets.id"), nullable=False)
    version_label: Mapped[str] = mapped_column(String(120), nullable=False)
    source_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    manual: Mapped["Manual"] = relationship("Manual", back_populates="versions")
    source_file_asset: Mapped["FileAsset"] = relationship("FileAsset", back_populates="versions")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="manual_version",
        cascade="all, delete-orphan",
        order_by="IngestionJob.created_at",
    )
    sections: Mapped[list["Section"]] = relationship(
        "Section",
        back_populates="manual_version",
        cascade="all, delete-orphan",
        order_by="Section.sort_order",
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk",
        back_populates="manual_version",
        cascade="all, delete-orphan",
        order_by="Chunk.sort_order",
    )
    source_pages: Mapped[list["SourcePage"]] = relationship(
        "SourcePage",
        back_populates="manual_version",
        cascade="all, delete-orphan",
        order_by="SourcePage.page_number",
    )

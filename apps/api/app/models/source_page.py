from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SourcePage(Base):
    __tablename__ = "source_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    manual_version_id: Mapped[str] = mapped_column(
        ForeignKey("manual_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    manual_version: Mapped["ManualVersion"] = relationship("ManualVersion", back_populates="source_pages")

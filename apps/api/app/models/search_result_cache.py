from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SearchResultCache(Base):
    __tablename__ = "search_results_cache"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    manual_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    results_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

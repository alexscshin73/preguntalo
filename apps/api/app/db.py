from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings


settings = get_settings()

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import (  # noqa: F401
        chunk,
        file_asset,
        ingestion_job,
        manual,
        manual_version,
        search_query_tag_stat,
        search_result_cache,
        section,
        source_page,
    )

    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
    _ensure_schema()


def _ensure_schema() -> None:
    inspector = inspect(engine)
    with engine.begin() as connection:
        manual_columns = {column["name"] for column in inspector.get_columns("manuals")}
        if "tags_json" not in manual_columns:
            connection.execute(text("ALTER TABLE manuals ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'"))

        section_columns = {column["name"] for column in inspector.get_columns("sections")}
        if "tags_json" not in section_columns:
            connection.execute(text("ALTER TABLE sections ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'"))

        version_columns = {column["name"] for column in inspector.get_columns("manual_versions")}
        if "tags_json" not in version_columns:
            connection.execute(text("ALTER TABLE manual_versions ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'"))

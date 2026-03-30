from collections import Counter
from datetime import datetime, timezone
import uuid
import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.ingestion_job import IngestionJob
from app.models.manual import Manual
from app.models.manual_version import ManualVersion
from app.models.search_result_cache import SearchResultCache
from app.models.section import Section
from app.models.source_page import SourcePage
from app.services.chunker import Chunker
from app.services.embedding import EmbeddingService
from app.services.parser import DocumentParser
from app.services.tags import TagService
from app.services.text import normalize_text

BILINGUAL_TAG_CANDIDATES = (
    ("로그인 / inicio de sesion", {"로그인", "login", "signin", "sesion", "iniciodesesion"}, "auth"),
    ("시작 / inicio", {"시작", "inicio", "primerospasos"}, "start"),
    ("메인 / pantalla principal", {"메인", "main", "pantallaprincipal"}, "main"),
    ("예약 / reserva", {"예약", "reserva"}, "reservation"),
    ("주문 / pedidos", {"주문", "pedido", "pedidos"}, "orders"),
    ("결제 / pago", {"결제", "pago", "pagos"}, "payment"),
    ("회원관리 / gestion clientes", {"회원관리", "gestionclientes", "cliente", "clientes"}, "customer"),
    ("시재정산 / caja liquidacion", {"시재정산", "시재", "정산", "caja", "liquidacion", "cajaliquidacion"}, "settlement"),
    ("마감 / cierre", {"마감", "마감하기", "cierre", "cerrar"}, "closing"),
    ("교대 / cambio de turno", {"교대", "cambio", "turno", "cambiodeturno"}, "shift"),
    ("권한 / permisos", {"권한", "permiso", "permisos"}, "permission"),
    ("고객 / clientes", {"고객", "cliente", "clientes"}, "customer"),
)


class IngestionService:
    """Temporary synchronous ingestion until Temporal workers are wired in."""

    def __init__(self) -> None:
        self.parser = DocumentParser()
        self.chunker = Chunker()
        self.embedding_service = EmbeddingService()
        self.tag_service = TagService()

    def enqueue_manual_version(self, db: Session, manual_version_id: str) -> IngestionJob:
        job = IngestionJob(
            id=f"ing_{uuid.uuid4().hex[:16]}",
            manual_version_id=manual_version_id,
            status="queued",
            workflow_name="manual_ingestion",
            detail="Upload stored and waiting for parsing.",
        )
        db.add(job)
        db.flush()
        return job

    def process_manual_version(
        self,
        db: Session,
        *,
        version: ManualVersion,
        job: IngestionJob,
        filename: str,
        content: bytes,
    ) -> tuple[int, int, int]:
        try:
            parsed_document = self.parser.parse(filename=filename, content=content)
            # Search answers depend on the indexed corpus, so clear cached answers
            # before replacing the stored sections/chunks for this version.
            db.execute(delete(SearchResultCache))
            db.execute(delete(Chunk).where(Chunk.manual_version_id == version.id))
            db.execute(delete(Section).where(Section.manual_version_id == version.id))
            db.execute(delete(SourcePage).where(SourcePage.manual_version_id == version.id))

            section_count = 0
            chunk_count = 0
            page_count = 0
            section_headings: list[str] = []
            section_bodies: list[str] = []

            for parsed_page in parsed_document.pages:
                db.add(
                    SourcePage(
                        manual_version_id=version.id,
                        page_number=parsed_page.page_number,
                        extracted_text=parsed_page.text or "",
                    )
                )
                page_count += 1

            for parsed_section in parsed_document.sections:
                body_text = parsed_section.body_text
                if not body_text:
                    continue

                section_language = parsed_section.language or version.source_language
                section = Section(
                    id=f"sec_{uuid.uuid4().hex[:16]}",
                    manual_version_id=version.id,
                    heading=parsed_section.heading,
                    heading_path=parsed_section.heading,
                    language=section_language,
                    page_start=parsed_section.page_start,
                    page_end=parsed_section.page_end,
                    sort_order=parsed_section.order,
                    body_text=body_text,
                    normalized_text=normalize_text(f"{parsed_section.heading} {body_text}"),
                    tags_json=self.tag_service.dump_tags(
                        self.tag_service.extract_tags(
                            parsed_section.heading,
                            body_text[:600],
                        )
                    ),
                )
                db.add(section)
                db.flush()
                section_count += 1
                section_headings.append(parsed_section.heading)
                section_bodies.append(body_text[:1200])

                chunk_candidates = self.chunker.split(parsed_section.body_lines)
                chunk_texts = [candidate.text for candidate in chunk_candidates]
                embeddings, embedding_model = self.embedding_service.embed_texts(chunk_texts)

                for index, candidate in enumerate(chunk_candidates, start=1):
                    text = candidate.text
                    if not text:
                        continue
                    embedding_vector = embeddings[index - 1] if index - 1 < len(embeddings) else None
                    chunk = Chunk(
                        id=f"chk_{uuid.uuid4().hex[:16]}",
                        section_id=section.id,
                        manual_version_id=version.id,
                        page_start=candidate.page_start,
                        page_end=candidate.page_end,
                        language=version.source_language,
                        chunk_text=text,
                        normalized_text=normalize_text(text),
                        token_count=self.chunker.estimate_tokens(text),
                        embedding=embedding_vector,
                        embedding_model=embedding_model,
                        sort_order=index,
                    )
                    db.add(chunk)
                    chunk_count += 1

            manual = version.manual or db.get(Manual, version.manual_id)
            generated_tags = self.collect_version_tags(
                version,
                section_headings=section_headings,
                section_bodies=section_bodies,
            )
            version.tags_json = self.tag_service.dump_tags(generated_tags)
            if manual is not None:
                manual.tags_json = self.tag_service.dump_tags(
                    self.tag_service.merge_tags(
                        self.tag_service.load_tags(manual.tags_json),
                        generated_tags,
                    )
                )
                manual.status = "active" if chunk_count else "requires_review"

            version.status = "indexed" if chunk_count else "failed"
            version.indexed_at = datetime.now(timezone.utc) if chunk_count else None
            job.status = "completed" if chunk_count else "failed"
            job.detail = f"Created {page_count} pages, {section_count} sections, and {chunk_count} chunks."
            db.flush()
            return page_count, section_count, chunk_count
        except Exception as exc:  # noqa: BLE001
            version.status = "failed"
            version.indexed_at = None
            job.status = "failed"
            job.detail = str(exc)
            db.flush()
            return 0, 0, 0

    def collect_version_tags(
        self,
        version: ManualVersion,
        *,
        section_headings: list[str] | None = None,
        section_bodies: list[str] | None = None,
    ) -> list[str]:
        headings = section_headings or [section.heading for section in version.sections]
        title_scores: Counter[str] = Counter()
        heading_scores: Counter[str] = Counter()

        self._score_bilingual_tags(title_scores, version.version_label, weight=6)
        filename = version.source_file_asset.original_filename if version.source_file_asset else ""
        if filename:
            self._score_bilingual_tags(title_scores, filename, weight=5)

        title_ranked = [tag for tag, _ in title_scores.most_common(8)]

        for heading in headings[:2]:
            self._score_bilingual_tags(heading_scores, heading, weight=2)

        heading_ranked = [tag for tag, _ in heading_scores.most_common(6)]
        combined_ranked = self._dedupe_generated_tags(
            [*title_ranked, *heading_ranked],
            source_language=version.source_language,
        )[:3]
        if combined_ranked:
            return combined_ranked

        return []

    def _score_bilingual_tags(self, scores: Counter[str], text: str, *, weight: int) -> None:
        if not text:
            return

        compact = normalize_text(text).replace(" ", "")
        for label, keywords, _family in BILINGUAL_TAG_CANDIDATES:
            if any(keyword in compact for keyword in keywords):
                scores[label] += weight

    def _pair_from_segments(self, left: str, right: str) -> str | None:
        clean_left = self._clean_tag_segment(left)
        clean_right = self._clean_tag_segment(right)
        if not clean_left or not clean_right:
            return None

        left_has_korean = bool(re.search(r"[가-힣]", clean_left))
        right_has_korean = bool(re.search(r"[가-힣]", clean_right))

        if left_has_korean == right_has_korean:
            return None

        korean = clean_left if left_has_korean else clean_right
        latin = clean_right if left_has_korean else clean_left
        return f"{korean} / {latin.lower()}"

    def _clean_tag_segment(self, value: str) -> str:
        cleaned = re.sub(r"^\d+[\s._-]*", "", value).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip(" -_/")
        cleaned = cleaned[:40]
        return cleaned

    def _dedupe_generated_tags(self, tags: list[str], *, source_language: str) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        seen_families: set[str] = set()
        seen_compact_keys: list[str] = []

        for tag in tags:
            family = self._family_for_tag(tag)
            if family and family in seen_families:
                continue

            key = self._tag_dedupe_key(tag, source_language=source_language)
            if not key or key in seen:
                continue

            # Keep conservative auto-tagging: if two tags are near-duplicates
            # like "예약" and "예약등록", retain only the earlier, stronger one.
            if any(key in existing or existing in key for existing in seen_compact_keys):
                continue

            if family:
                seen_families.add(family)
            seen.add(key)
            seen_compact_keys.append(key)
            deduped.append(tag)

        return deduped

    def _family_for_tag(self, tag: str) -> str:
        normalized = normalize_text(tag).replace(" ", "")
        for label, _keywords, family in BILINGUAL_TAG_CANDIDATES:
            if normalize_text(label).replace(" ", "") == normalized:
                return family
        return ""

    def _tag_dedupe_key(self, tag: str, *, source_language: str) -> str:
        trimmed = tag.strip()
        if not trimmed:
            return ""

        if "/" in trimmed:
            left, right = [part.strip().lower() for part in trimmed.split("/", 1)]
            return right if source_language == "es" else left

        return normalize_text(trimmed).replace(" ", "")

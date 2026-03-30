import hashlib
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
import re
import uuid

from sqlalchemy import Float, case, delete, func, literal, literal_column, or_, select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.manual import Manual
from app.models.manual_version import ManualVersion
from app.models.search_query_tag_stat import SearchQueryTagStat
from app.models.section import Section
from app.models.source_page import SourcePage
from app.models.search_result_cache import SearchResultCache
from app.services.embedding import EmbeddingService
from app.services.tags import TagService
from app.schemas.search import (
    CitationItem,
    PopularQueryTagItem,
    PopularQueryTagResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SectionDetailResponse,
    ViewerPageResponse,
)

SEARCH_STOPWORDS = {
    "a",
    "about",
    "como",
    "con",
    "de",
    "del",
    "do",
    "el",
    "en",
    "es",
    "for",
    "how",
    "la",
    "las",
    "lo",
    "los",
    "manual",
    "manuales",
    "para",
    "por",
    "que",
    "se",
    "system",
    "the",
    "un",
    "una",
    "y",
    "가",
    "것",
    "관련",
    "궁금한",
    "대한",
    "등록",
    "매뉴얼",
    "방법",
    "사용",
    "사용법",
    "설명",
    "시",
    "시스템",
    "안내",
    "어떻게",
    "절차",
    "좀",
    "페이지",
    "해",
    "해줘",
    "확인",
}

KOREAN_PARTICLES = [
    "으로",
    "에서",
    "에게",
    "까지",
    "부터",
    "처럼",
    "보다",
    "하고",
    "이며",
    "이다",
    "라고",
    "이라",
    "하면",
    "하기",
    "하다",
    "해요",
    "해줘",
    "입니다",
    "있는",
    "되는",
    "하려면",
    "하는",
    "할",
    "한",
    "을",
    "를",
    "이",
    "가",
    "은",
    "는",
    "에",
    "와",
    "과",
    "도",
    "로",
]

KOREAN_VERB_ENDINGS = [
    "해주세요",
    "해줘요",
    "알려줘",
    "보여줘",
    "찾아줘",
    "설명해",
    "설명해줘",
    "해줘",
    "해요",
    "합니다",
    "했다",
    "하다",
    "하기",
    "하면",
    "하는",
    "하라",
    "할까",
    "될까",
    "되는",
    "됩니다",
    "되나요",
    "있나요",
    "없나요",
    "주세요",
]

GENERIC_HEADINGS = {"사용방법", "사용 방법", "manual usage", "imported content"}
GENERIC_VERSION_LABELS = {"readme", "guide", "manual"}
QUALITY_EXPANSIONS = {
    "로그인": {"login", "signin", "접속", "아이디", "비밀번호", "sesion"},
    "login": {"로그인", "접속", "signin", "sesion"},
    "pos": {"gdr", "screen", "bar", "terminal"},
    "password": {"비밀번호", "clave"},
    "비밀번호": {"password", "clave"},
    "마감": {"마감하기", "cierre", "정산", "liquidacion", "caja"},
    "마감하기": {"마감", "cierre", "정산", "liquidacion", "caja"},
    "정산": {"liquidacion", "caja", "마감", "마감하기"},
    "교대": {"cambio", "turno"},
    "예약": {"reserva"},
}

INTENT_GROUPS = {
    "login": {"로그인", "login", "signin", "접속", "아이디", "비밀번호", "sesion", "pos", "gdr", "screen", "bar"},
    "closing": {"마감", "마감하기", "cierre", "정산", "liquidacion", "caja"},
    "shift": {"교대", "turno", "cambio"},
    "reservation": {"예약", "reserva"},
    "payment": {"결제", "pago", "payment"},
    "customer": {"회원", "고객", "cliente", "clientes"},
}

INTENT_ACTION_SIGNALS = {
    "login": {
        "본인의아이디로로그인",
        "로그인후pos선택",
        "pos선택화면",
        "pagdr",
        "pbscreen",
        "bar를선택",
    },
    "closing": {
        "영업을마무리",
        "마감하기버튼",
        "확인및서명하기",
        "마감정산영수증",
        "마감이완료",
    },
    "shift": {
        "교대하기버튼",
        "교대정산영수증",
        "교대할직원",
    },
}

POPULAR_TAG_BLOCKLIST = {
    "como",
    "cómo",
    "cómopuedo",
    "explica",
    "hacer",
    "hay",
    "puedo",
    "que",
    "qué",
    "하나",
    "하나요",
    "해요",
}


class SearchService:
    CACHE_TTL = timedelta(minutes=1)
    DB_FETCH_LIMIT = 500
    BM25_WEIGHT = 0.58
    VECTOR_WEIGHT = 0.18
    TAG_WEIGHT = 0.1
    HEADING_WEIGHT = 0.24
    PHRASE_WEIGHT = 0.16
    SPECIFICITY_WEIGHT = 0.08
    POPULAR_TAG_MIN = 3
    POPULAR_TAG_MAX = 15

    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()
        self.tag_service = TagService()

    def search(self, db: Session, payload: SearchRequest) -> SearchResponse:
        explicit_tags = self._normalize_payload_tags(payload.tags)
        extracted_tags = self.tag_service.extract_tags(payload.query, limit=6)
        query_tags = self.tag_service.merge_tags(explicit_tags, extracted_tags, limit=8)
        self._record_query_tags(db, query_tags)
        query_text = self._expanded_query_text(payload.query, query_tags)

        query_hash = self._hash_query(payload)
        cached = self._load_cached_response(db, query_hash, payload)
        if cached is not None:
            return cached

        query_terms = self._query_terms(query_text, expand_synonyms=True)
        query_embedding, query_embedding_model = self.embedding_service.embed_text(query_text)

        rows = self._execute_db_search(db, payload, query_embedding, query_text)
        results = self._rank_results(
            rows,
            payload,
            query_tags,
            query_terms,
            query_embedding,
            query_embedding_model,
        )

        limited = self._prune_results(results)[: payload.top_k]
        if limited:
            self._cache_response(db, query_hash, payload, query_tags, limited)
        return SearchResponse(queryLanguage=payload.language, queryTags=query_tags, results=limited)

    def popular_query_tags(self, db: Session, limit: int = 8) -> PopularQueryTagResponse:
        normalized_limit = min(max(limit, self.POPULAR_TAG_MIN), self.POPULAR_TAG_MAX)
        rows = db.scalars(
            select(SearchQueryTagStat)
            .order_by(SearchQueryTagStat.query_count.desc(), SearchQueryTagStat.updated_at.desc())
            .limit(normalized_limit)
        ).all()

        aggregated_counts: Counter[str] = Counter()
        for row in rows:
            normalized_tags = self.tag_service.extract_tags(row.tag, limit=1)
            if not normalized_tags:
                continue
            candidate_tag = normalized_tags[0]
            if not self._is_displayable_popular_tag(candidate_tag):
                continue
            aggregated_counts[candidate_tag] += row.query_count

        ranked_counts = aggregated_counts.most_common(normalized_limit)
        items = [
            PopularQueryTagItem(tag=tag, queryCount=count)
            for tag, count in ranked_counts
            if not any(other_tag != tag and len(other_tag) > len(tag) and tag in other_tag for other_tag in aggregated_counts)
        ]

        if len(items) < self.POPULAR_TAG_MIN:
            existing_tags = {item.tag for item in items}
            for tag, count in ranked_counts:
                if tag in existing_tags:
                    continue
                items.append(PopularQueryTagItem(tag=tag, queryCount=count))
                existing_tags.add(tag)
                if len(items) >= min(self.POPULAR_TAG_MIN, normalized_limit):
                    break

        if len(items) < self.POPULAR_TAG_MIN:
            fallback_tags = self._fallback_popular_tags(
                db,
                limit=normalized_limit,
                excluded_tags={item.tag for item in items},
            )
            for tag, count in fallback_tags:
                if not self._is_displayable_popular_tag(tag):
                    continue
                items.append(PopularQueryTagItem(tag=tag, queryCount=count))
                if len(items) >= normalized_limit:
                    break

        return PopularQueryTagResponse(items=items[:normalized_limit])

    def get_section_detail(self, db: Session, section_id: str, language: str) -> SectionDetailResponse | None:
        row = db.execute(
            select(Section, ManualVersion, Manual)
            .join(ManualVersion, Section.manual_version_id == ManualVersion.id)
            .join(Manual, ManualVersion.manual_id == Manual.id)
            .where(Section.id == section_id)
        ).first()
        if row is None:
            return None

        section, version, manual = row
        return SectionDetailResponse(
            sectionId=section.id,
            summaryLanguage=language,
            summary=self._summary_for_language(language, section.body_text),
            tags=self.tag_service.merge_tags(
                self.tag_service.load_tags(section.tags_json),
                self.tag_service.load_tags(version.tags_json),
                self.tag_service.load_tags(manual.tags_json),
                limit=8,
            ),
            citations=[
                CitationItem(
                    page=section.page_start,
                    label=self._citation_label(language),
                    viewerUrl=f"/viewer/{manual.id}/{version.id}?page={section.page_start}&section={section.id}",
                )
            ],
            relatedImages=[],
        )

    def get_viewer_page(
        self,
        db: Session,
        *,
        manual_id: str,
        version_id: str,
        page_number: int,
        section_id: str | None = None,
    ) -> ViewerPageResponse | None:
        version_row = db.execute(
            select(ManualVersion, Manual)
            .join(Manual, ManualVersion.manual_id == Manual.id)
            .where(ManualVersion.id == version_id, Manual.id == manual_id)
        ).first()
        if version_row is None:
            return None

        version, manual = version_row
        page = db.scalar(
            select(SourcePage).where(
                SourcePage.manual_version_id == version.id,
                SourcePage.page_number == page_number,
            )
        )
        if page is None:
            return None

        total_pages = db.scalar(
            select(func.count()).select_from(SourcePage).where(SourcePage.manual_version_id == version.id)
        ) or 0
        section_heading: str | None = None
        matched_section_id: str | None = None

        if section_id:
            section = db.scalar(
                select(Section).where(
                    Section.id == section_id,
                    Section.manual_version_id == version.id,
                )
            )
            if section is not None:
                matched_section_id = section.id
                section_heading = section.heading

        return ViewerPageResponse(
            manualId=manual.id,
            manualTitle=manual.title,
            versionId=version.id,
            versionLabel=version.version_label,
            pageNumber=page.page_number,
            totalPages=total_pages,
            extractedText=page.extracted_text or "",
            sectionId=matched_section_id,
            sectionHeading=section_heading,
        )

    def _execute_db_search(
        self,
        db: Session,
        payload: SearchRequest,
        query_embedding: list[float] | None,
        query_text: str,
    ):
        engine_name = db.get_bind().dialect.name if db.get_bind() else ""
        if engine_name == "postgresql":
            return self._execute_postgres_search(db, payload, query_embedding, query_text)
        return self._execute_fallback_search(db, payload, query_text)

    def _execute_postgres_search(
        self,
        db: Session,
        payload: SearchRequest,
        query_embedding: list[float] | None,
        query_text: str,
    ):
        ts_query = func.plainto_tsquery("simple", query_text)
        text_vector = func.to_tsvector("simple", Chunk.normalized_text)
        bm25_score = func.coalesce(func.ts_rank_cd(text_vector, ts_query), 0.0).label("bm25_score")

        if query_embedding:
            vector_distance = Chunk.embedding.op("<=>")(query_embedding).label("vector_distance")
        else:
            vector_distance = literal_column("NULL").label("vector_distance")

        statement = (
            select(Chunk, Section, ManualVersion, Manual, bm25_score, vector_distance)
            .join(Section, Chunk.section_id == Section.id)
            .join(ManualVersion, Chunk.manual_version_id == ManualVersion.id)
            .join(Manual, ManualVersion.manual_id == Manual.id)
            .where(
                or_(
                    ManualVersion.status == "indexed",
                    ManualVersion.indexed_at.is_not(None),
                )
            )
        )

        if payload.manual_ids:
            statement = statement.where(Manual.id.in_(payload.manual_ids))

        statement = statement.order_by(bm25_score.desc(), vector_distance.asc().nullslast()).limit(self.DB_FETCH_LIMIT)
        return db.execute(statement).all()

    def _execute_fallback_search(self, db: Session, payload: SearchRequest, query_text: str):
        query_terms = self._query_terms(query_text, expand_synonyms=True)
        match_count = literal(0.0, type_=Float)

        for term in query_terms:
            match_count = match_count + case(
                (func.lower(Chunk.normalized_text).like(f"%{term}%"), 1.0),
                else_=0.0,
            )

        bm25_score = (
            (match_count / max(len(query_terms), 1)).cast(Float).label("bm25_score")
            if query_terms
            else literal(0.0, type_=Float).label("bm25_score")
        )
        vector_distance = literal_column("NULL").label("vector_distance")

        statement = (
            select(Chunk, Section, ManualVersion, Manual, bm25_score, vector_distance)
            .join(Section, Chunk.section_id == Section.id)
            .join(ManualVersion, Chunk.manual_version_id == ManualVersion.id)
            .join(Manual, ManualVersion.manual_id == Manual.id)
            .where(
                or_(
                    ManualVersion.status == "indexed",
                    ManualVersion.indexed_at.is_not(None),
                )
            )
        )

        if payload.manual_ids:
            statement = statement.where(Manual.id.in_(payload.manual_ids))

        statement = statement.order_by(bm25_score.desc(), Chunk.created_at.desc()).limit(self.DB_FETCH_LIMIT)
        return db.execute(statement).all()

    def _rank_results(
        self,
        rows,
        payload: SearchRequest,
        query_tags: list[str],
        query_terms: list[str],
        query_embedding: list[float] | None,
        query_embedding_model: str | None,
    ) -> list[SearchResultItem]:
        scored_sections: dict[str, tuple[float, SearchResultItem]] = {}

        for chunk, section, version, manual, bm25_score, vector_distance in rows:
            bm25_value = float(bm25_score or 0.0)
            if bm25_value <= 0:
                bm25_value = self._fallback_text_score(query_terms, section.heading, chunk.chunk_text)
            vector_similarity = 0.0
            if self._should_use_vector_similarity(query_embedding_model, chunk.embedding_model):
                vector_similarity = self._vector_similarity(vector_distance)
            if (
                vector_similarity <= 0
                and query_embedding is not None
                and chunk.embedding is not None
                and self._should_use_vector_similarity(query_embedding_model, chunk.embedding_model)
            ):
                vector_similarity = self.embedding_service.cosine_similarity(query_embedding, chunk.embedding)
            tag_score = self._tag_match_score(query_tags, manual, version, section)
            heading_score = self._heading_match_score(query_terms, section.heading)
            phrase_score = self._phrase_match_score(payload.query, section.heading, chunk.chunk_text)
            specificity_score = self._specificity_score(query_terms, section.heading, chunk.chunk_text)
            intent_bonus = self._intent_alignment_bonus(query_terms, version.version_label, section.heading, chunk.chunk_text)
            intent_penalty = self._intent_mismatch_penalty(query_terms, version.version_label, section.heading, chunk.chunk_text)
            action_signal_bonus = self._action_signal_bonus(
                query_terms,
                version.version_label,
                section.heading,
                chunk.chunk_text,
            )
            generic_penalty = self._generic_penalty(payload.query, version.version_label, section.heading)

            score = (
                bm25_value * self.BM25_WEIGHT
                + vector_similarity * self.VECTOR_WEIGHT
                + tag_score * self.TAG_WEIGHT
                + heading_score * self.HEADING_WEIGHT
                + phrase_score * self.PHRASE_WEIGHT
                + specificity_score * self.SPECIFICITY_WEIGHT
                + intent_bonus
                + action_signal_bonus
                - intent_penalty
                - generic_penalty
            )

            if score <= 0:
                continue

            item = SearchResultItem(
                sectionId=section.id,
                manualId=manual.id,
                manualTitle=manual.title,
                versionId=version.id,
                versionLabel=version.version_label,
                heading=section.heading,
                snippet=self._snippet(chunk.chunk_text),
                score=round(score, 4),
                pageStart=section.page_start,
                pageEnd=section.page_end,
                detailUrl=f"/viewer/{manual.id}/{version.id}?page={section.page_start}&section={section.id}",
                tags=self.tag_service.merge_tags(
                    self.tag_service.load_tags(section.tags_json),
                    self.tag_service.load_tags(version.tags_json),
                    self.tag_service.load_tags(manual.tags_json),
                    limit=6,
                ),
            )

            existing = scored_sections.get(section.id)
            if existing is None or score > existing[0]:
                scored_sections[section.id] = (score, item)

        ranked = [item for _, item in sorted(scored_sections.values(), key=lambda entry: entry[0], reverse=True)]
        return ranked

    def _hash_query(self, payload: SearchRequest) -> str:
        manual_key = "|".join(sorted(payload.manual_ids))
        tag_key = "|".join(sorted(self._normalize_payload_tags(payload.tags)))
        fingerprint = f"{payload.language}|{payload.query}|{tag_key}|{manual_key}|{payload.top_k}"
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _load_cached_response(self, db: Session, query_hash: str, payload: SearchRequest) -> SearchResponse | None:
        now = datetime.now(timezone.utc)
        cache = db.scalar(
            select(SearchResultCache)
            .where(SearchResultCache.query_hash == query_hash)
            .where(SearchResultCache.language == payload.language)
            .where(SearchResultCache.top_k == payload.top_k)
            .where(SearchResultCache.expires_at > now)
        )
        if cache is None:
            return None

        data = json.loads(cache.results_json)
        results = [SearchResultItem.parse_obj(item) for item in data.get("results", [])]
        if not results:
            db.delete(cache)
            db.commit()
            return None
        return SearchResponse(queryLanguage=payload.language, queryTags=data.get("query_tags", []), results=results)

    def _cache_response(
        self,
        db: Session,
        query_hash: str,
        payload: SearchRequest,
        query_tags: list[str],
        results: list[SearchResultItem],
    ) -> None:
        now = datetime.now(timezone.utc)
        db.execute(
            delete(SearchResultCache).where(
                SearchResultCache.query_hash == query_hash,
                SearchResultCache.language == payload.language,
                SearchResultCache.top_k == payload.top_k,
            )
        )
        db.execute(delete(SearchResultCache).where(SearchResultCache.expires_at <= now))
        cache = SearchResultCache(
            id=f"cache_{uuid.uuid4().hex[:16]}",
            query_hash=query_hash,
            language=payload.language,
            manual_ids_json=json.dumps(sorted(payload.manual_ids), ensure_ascii=False),
            top_k=payload.top_k,
            results_json=json.dumps(
                {"query_tags": query_tags, "results": [result.dict(by_alias=True) for result in results]},
                ensure_ascii=False,
            ),
            expires_at=now + self.CACHE_TTL,
        )
        db.add(cache)
        db.commit()

    def _record_query_tags(self, db: Session, query_tags: list[str]) -> None:
        for tag in query_tags:
            normalized_tag = self.tag_service.normalize_tag(tag)
            if not normalized_tag:
                continue

            existing = db.get(SearchQueryTagStat, normalized_tag)
            if existing is None:
                db.add(SearchQueryTagStat(tag=normalized_tag, query_count=1))
                continue

            existing.query_count += 1

        db.commit()

    def _is_displayable_popular_tag(self, tag: str) -> bool:
        if len(tag) < 2 or len(tag) > 16:
            return False
        if tag in POPULAR_TAG_BLOCKLIST:
            return False
        if any(tag.endswith(suffix) for suffix in ("하나", "하나요", "puedo", "hacer")):
            return False
        return True

    def _normalize_payload_tags(self, tags: list[str]) -> list[str]:
        normalized: list[str] = []
        for tag in tags:
            clean = self.tag_service.normalize_tag(tag.lstrip("#"))
            if clean:
                normalized.append(clean)
        return self.tag_service.merge_tags(normalized, limit=8)

    def _expanded_query_text(self, query: str, query_tags: list[str]) -> str:
        if not query_tags:
            return query
        return " ".join([query.strip(), *query_tags]).strip()

    def _fallback_popular_tags(
        self,
        db: Session,
        *,
        limit: int,
        excluded_tags: set[str],
    ) -> list[tuple[str, int]]:
        tag_counts: Counter[str] = Counter()
        manuals = db.scalars(select(Manual).order_by(Manual.created_at.desc())).all()

        for manual in manuals:
            for tag in self.tag_service.load_tags(manual.tags_json):
                normalized_tag = self.tag_service.normalize_tag(tag)
                if normalized_tag and normalized_tag not in excluded_tags:
                    tag_counts[normalized_tag] += 1

            for version in manual.versions:
                for tag in self.tag_service.load_tags(version.tags_json):
                    normalized_tag = self.tag_service.normalize_tag(tag)
                    if normalized_tag and normalized_tag not in excluded_tags:
                        tag_counts[normalized_tag] += 1

                for section in version.sections:
                    for tag in self.tag_service.load_tags(section.tags_json):
                        normalized_tag = self.tag_service.normalize_tag(tag)
                        if normalized_tag and normalized_tag not in excluded_tags:
                            tag_counts[normalized_tag] += 1

        return tag_counts.most_common(limit)

    def _vector_similarity(self, distance: float | None) -> float:
        if distance is None:
            return 0.0
        return 1.0 / (1.0 + max(distance, 0.0))

    def _should_use_vector_similarity(
        self,
        query_embedding_model: str | None,
        chunk_embedding_model: str | None,
    ) -> bool:
        if not query_embedding_model or not chunk_embedding_model:
            return False
        return not (
            query_embedding_model.startswith("local-hash")
            or chunk_embedding_model.startswith("local-hash")
        )

    def _tag_match_score(
        self,
        query_tags: list[str],
        manual: Manual,
        version: ManualVersion,
        section: Section,
    ) -> float:
        raw_tags = (
            self.tag_service.load_tags(section.tags_json)
            + self.tag_service.load_tags(version.tags_json)
            + self.tag_service.load_tags(manual.tags_json)
        )
        tag_pool = set(raw_tags)
        for raw_tag in raw_tags:
            tag_pool.update(self.tag_service.extract_tags(raw_tag, limit=6))
        if not query_tags:
            return 0.0
        matches = sum(1 for tag in query_tags if tag in tag_pool)
        return matches / len(query_tags)

    def _snippet(self, text: str) -> str:
        compact = re.sub(r"[\x00-\x1f\x7f]", " ", text)
        compact = " ".join(compact.split())
        return compact[:180] + ("..." if len(compact) > 180 else "")

    def _query_terms(self, query: str, *, expand_synonyms: bool = False) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()

        for raw_token in re.findall(r"[\w가-힣áéíóúñü]+", query.lower()):
            token = self._normalize_query_token(raw_token)
            if not token or token in seen:
                continue

            seen.add(token)
            terms.append(token)

            if expand_synonyms:
                for expanded in QUALITY_EXPANSIONS.get(token, set()):
                    normalized_expanded = self._normalize_query_token(expanded)
                    if not normalized_expanded or normalized_expanded in seen:
                        continue
                    seen.add(normalized_expanded)
                    terms.append(normalized_expanded)

        return terms

    def _fallback_text_score(self, query_terms: list[str], heading: str, body: str) -> float:
        if not query_terms:
            return 0.0

        haystack_terms = set(self._query_terms(f"{heading} {body}"))
        if not haystack_terms:
            return 0.0

        matches = sum(1 for term in query_terms if term in haystack_terms)
        return matches / len(query_terms)

    def _heading_match_score(self, query_terms: list[str], heading: str) -> float:
        normalized_heading = self._normalize_query_token(heading)
        heading_terms = set(self._query_terms(heading))
        if not heading_terms:
            return 0.0

        score = 0.0
        for term in query_terms:
            if term in heading_terms:
                score += 1.0
            elif term and term in normalized_heading:
                score += 0.7

        return min(score / max(len(query_terms), 1), 1.0)

    def _phrase_match_score(self, query: str, heading: str, body: str) -> float:
        normalized_query = self._normalize_query_token(query)
        normalized_heading = self._normalize_query_token(heading)
        normalized_body = self._normalize_query_token(body)
        if not normalized_query:
            return 0.0

        if normalized_query in normalized_heading:
            return 1.0
        if normalized_query in normalized_body:
            return 0.75

        return 0.0

    def _specificity_score(self, query_terms: list[str], heading: str, body: str) -> float:
        text = self._normalize_query_token(f"{heading} {body}")
        if not text or not query_terms:
            return 0.0

        exact_matches = sum(1 for term in query_terms if term and term in text)
        if exact_matches == 0:
            return 0.0

        keyword_bonus = 0.0
        if "로그인" in query_terms and any(token in text for token in {"로그인", "login", "sesion"}):
            keyword_bonus += 0.4
        if "pos" in query_terms and any(token in text for token in {"pos", "screen", "gdr", "bar"}):
            keyword_bonus += 0.4
        if "비밀번호" in query_terms and any(token in text for token in {"비밀번호", "password", "clave"}):
            keyword_bonus += 0.3

        base_score = exact_matches / len(query_terms)
        return min(base_score + keyword_bonus, 1.0)

    def _query_intent_groups(self, query_terms: list[str]) -> set[str]:
        matched_groups: set[str] = set()
        term_set = set(query_terms)
        for group_name, keywords in INTENT_GROUPS.items():
            if term_set & keywords:
                matched_groups.add(group_name)
        return matched_groups

    def _intent_alignment_bonus(self, query_terms: list[str], version_label: str, heading: str, body: str) -> float:
        groups = self._query_intent_groups(query_terms)
        if not groups:
            return 0.0

        text = self._normalize_query_token(f"{version_label} {heading} {body}")
        bonus = 0.0

        for group_name in groups:
            keywords = INTENT_GROUPS[group_name]
            matches = sum(1 for keyword in keywords if keyword and keyword in text)
            if matches > 0:
                bonus += min(0.2 * matches, 0.6)

        return bonus

    def _intent_mismatch_penalty(self, query_terms: list[str], version_label: str, heading: str, body: str) -> float:
        groups = self._query_intent_groups(query_terms)
        if not groups:
            return 0.0

        text = self._normalize_query_token(f"{version_label} {heading} {body}")
        penalty = 0.0

        for group_name in groups:
            keywords = INTENT_GROUPS[group_name]
            if any(keyword in text for keyword in keywords):
                continue

            if group_name == "closing" and any(keyword in text for keyword in INTENT_GROUPS["reservation"]):
                penalty += 0.55
            elif group_name == "login" and any(
                keyword in text
                for keyword in (INTENT_GROUPS["reservation"] | INTENT_GROUPS["payment"] | INTENT_GROUPS["customer"])
            ):
                penalty += 0.45
            else:
                penalty += 0.18

        return penalty

    def _action_signal_bonus(self, query_terms: list[str], version_label: str, heading: str, body: str) -> float:
        groups = self._query_intent_groups(query_terms)
        if not groups:
            return 0.0

        text = self._normalize_query_token(f"{version_label} {heading} {body}")
        bonus = 0.0

        for group_name in groups:
            signals = INTENT_ACTION_SIGNALS.get(group_name, set())
            if not signals:
                continue

            matches = sum(1 for signal in signals if signal in text)
            if matches <= 0:
                continue

            bonus += min(0.14 * matches, 0.42)

        return bonus

    def _generic_penalty(self, query: str, version_label: str, heading: str) -> float:
        query_terms = set(self._query_terms(query, expand_synonyms=True))
        query_is_manual_management = bool(
            {"업로드", "파일", "매뉴얼", "인덱싱", "worker", "ingestion"} & query_terms
        )
        if query_is_manual_management:
            return 0.0

        normalized_heading = self._normalize_query_token(heading)
        normalized_version = self._normalize_query_token(version_label)
        penalty = 0.0

        if normalized_heading in GENERIC_HEADINGS:
            penalty += 0.18
        if normalized_version in GENERIC_VERSION_LABELS:
            penalty += 0.12

        return penalty

    def _prune_results(self, ranked: list[SearchResultItem]) -> list[SearchResultItem]:
        if not ranked:
            return ranked

        top_score = ranked[0].score
        minimum_score = max(top_score * 0.45, 0.08)
        return [item for item in ranked if item.score >= minimum_score]

    def _normalize_query_token(self, token: str) -> str:
        normalized = re.sub(r"[\x00-\x1f\x7f]", " ", token.lower())
        normalized = re.sub(r"[^\w\s가-힣áéíóúñü]", " ", normalized)
        normalized = " ".join(normalized.split())

        if not normalized:
            return ""

        compact = normalized.replace(" ", "")
        for particle in KOREAN_PARTICLES:
            if len(compact) > len(particle) + 1 and compact.endswith(particle):
                compact = compact[: -len(particle)]
                break

        for ending in KOREAN_VERB_ENDINGS:
            if len(compact) > len(ending) + 1 and compact.endswith(ending):
                compact = compact[: -len(ending)]
                break

        if len(compact) < 2 or compact in SEARCH_STOPWORDS:
            return ""

        return compact

    def _summary_for_language(self, language: str, body_text: str) -> str:
        compact = " ".join(body_text.split())
        sentences = re.split(r"(?<=[.!?])\s+", compact)
        picked = " ".join(sentences[:2]).strip()
        if picked:
            summary_body = picked
        else:
            summary_body = compact[:280] + ("..." if len(compact) > 280 else "")

        summaries = {
            "ko": f"이 절의 핵심 내용입니다: {summary_body}",
            "es": f"Resumen de esta seccion: {summary_body}",
            "en": f"Summary of this section: {summary_body}",
        }
        return summaries.get(language, summaries["en"])

    def _citation_label(self, language: str) -> str:
        labels = {
            "ko": "원문 보기",
            "es": "Ver original",
            "en": "View source",
        }
        return labels.get(language, labels["en"])

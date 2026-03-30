import httpx
import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.source_page import SourcePage
from app.schemas.search import (
    AnswerCitationItem,
    AnswerRequest,
    AnswerResponse,
    SearchRequest,
    SearchResultItem,
)
from app.services.search import SearchService

PROCEDURE_HINTS = {
    "ko": ("방법", "어떻게", "절차", "순서", "하려면", "할까", "할때", "때는"),
    "es": ("como", "pasos", "procedimiento", "manera"),
    "en": ("how", "steps", "procedure", "way"),
}

INTENT_EXPANSIONS = {
    "로그인": {"login", "signin", "접속", "아이디", "비밀번호"},
    "login": {"로그인", "signin", "sesion", "usuario", "clave"},
    "pos": {"screen", "gdr", "bar", "terminal"},
    "비밀번호": {"password", "clave"},
}

KOREAN_QUERY_PARTICLES = (
    "으로",
    "에서",
    "에게",
    "까지",
    "부터",
    "하고",
    "이며",
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
)

QUERY_STOPWORDS = {"어떻게", "하나요", "방법", "절차", "순서", "해주세요", "알려줘"}

KOREAN_ACTION_CUES = (
    "처음 시스템",
    "본인의 아이디",
    "로그인 후",
    "POS 선택",
    "영업 존",
    "현재는",
    "영업을 마무리",
    "시재 / 정산 화면",
    "시재/정산 화면",
    "그러면",
    "입력이 끝나면",
    "그 후",
    "먼저",
    "이후",
)


class AnswerService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.search_service = SearchService()
        self.base_url = self.settings.local_ai_base_url.rstrip("/")
        self.model = self.settings.local_chat_model
        self.timeout = self.settings.local_ai_timeout_seconds

    def answer(self, db: Session, payload: AnswerRequest) -> AnswerResponse:
        search_response = self.search_service.search(
            db,
            SearchRequest(
                query=payload.query,
                language=payload.language,
                tags=payload.tags,
                manualIds=payload.manual_ids,
                topK=payload.top_k,
            ),
        )
        answer_text, answer_source = self._build_answer(
            db=db,
            query=payload.query,
            language=payload.language,
            results=search_response.results,
        )
        citations = self._build_citations(payload.query, payload.language, search_response.results)
        return AnswerResponse(
            queryLanguage=search_response.query_language,
            queryTags=search_response.query_tags,
            answer=answer_text,
            answerSource=answer_source,
            citations=citations,
            results=search_response.results,
        )

    def _build_answer(
        self,
        *,
        db: Session,
        query: str,
        language: str,
        results: list[SearchResultItem],
    ) -> tuple[str, str]:
        if not results:
            return self._no_result_message(language), "local-fallback"

        generated = self._generate_with_local_model(query=query, language=language, results=results)
        if generated:
            return generated, f"ollama:{self.model}"

        return self._fallback_answer(db=db, query=query, language=language, results=results), "local-fallback"

    def _generate_with_local_model(
        self,
        *,
        query: str,
        language: str,
        results: list[SearchResultItem],
    ) -> str | None:
        context_blocks = []
        for index, result in enumerate(results[:5], start=1):
            context_blocks.append(
                "\n".join(
                    [
                        f"[{index}] manual={result.manual_title}",
                        f"heading={result.heading}",
                        f"pages={result.page_start}-{result.page_end}",
                        f"snippet={result.snippet}",
                        f"tags={', '.join(result.tags)}",
                    ]
                )
            )

        system_prompt = (
            "You answer questions strictly from the provided manual evidence. "
            "If the evidence is insufficient, say so clearly. "
            "Keep the answer concise and practical. "
            "Mention page numbers in plain text when helpful."
        )
        if language == "ko":
            system_prompt += " Respond in Korean."
        elif language == "es":
            system_prompt += " Respond in Spanish."

        user_prompt = "\n\n".join(
            [
                f"Question: {query}",
                "Evidence:",
                "\n\n".join(context_blocks),
            ]
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "stream": False,
                        "options": {"temperature": 0.1},
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:  # noqa: BLE001
            return None

        message = payload.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

        content = payload.get("response")
        if isinstance(content, str) and content.strip():
            return content.strip()

        return None

    def _fallback_answer(self, *, db: Session, query: str, language: str, results: list[SearchResultItem]) -> str:
        top = results[0]
        secondary = [
            item
            for item in results[1:5]
            if item.score >= max(top.score * 0.65, 0.12)
        ][:2]
        intent_tokens = self._intent_tokens(query)
        primary_results = self._select_primary_evidence(results, intent_tokens)

        if self._is_procedure_question(query, language):
            procedure_answer = self._build_procedure_answer(
                db=db,
                query=query,
                language=language,
                primary_results=primary_results,
                secondary=secondary,
            )
            if procedure_answer:
                return procedure_answer

        if language == "ko":
            lead = self._best_snippet_for_language(top, language)
            lines = [
                f"{top.manual_title}의 '{top.heading}' 내용을 기준으로 보면 {lead}",
            ]
            if secondary:
                lines.append("관련 근거는 아래 문서를 참고하세요.")
            return " ".join(lines)

        if language == "es":
            lead = self._best_snippet_for_language(top, language)
            lines = [
                f"Segun '{top.heading}' en {top.manual_title}, {lead}",
            ]
            if secondary:
                lines.append("Revise los documentos base de abajo para mas detalle.")
            return " ".join(lines)

        lead = self._best_snippet_for_language(top, language)
        return f"Based on '{top.heading}' in {top.manual_title}, {lead} See the supporting references below."

    def _no_result_message(self, language: str) -> str:
        if language == "ko":
            return "등록된 매뉴얼에서 직접 근거를 찾지 못했습니다. 질문 표현을 더 구체적으로 바꾸거나 태그를 추가해 다시 시도해 주세요."
        if language == "es":
            return "No encontre evidencia directa en los manuales registrados. Intente con una pregunta mas especifica o agregue tags."
        return "I could not find direct evidence in the registered manuals. Please try a more specific question."

    def _build_citations(
        self,
        query: str,
        language: str,
        results: list[SearchResultItem],
    ) -> list[AnswerCitationItem]:
        citations: list[AnswerCitationItem] = []
        seen: set[str] = set()
        ordered_results = results

        if self._is_procedure_question(query, language):
            intent_tokens = self._intent_tokens(query)
            primary_results = self._select_primary_evidence(results, intent_tokens)
            prioritized = self._prioritize_procedure_results(primary_results, intent_tokens)
            used_sections = {item.section_id for item in prioritized}
            ordered_results = prioritized + [item for item in results if item.section_id not in used_sections]

        for item in ordered_results[:5]:
            key = f"{item.manual_id}:{item.version_id}:{item.section_id}:{item.page_start}:{item.page_end}"
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                AnswerCitationItem(
                    sectionId=item.section_id,
                    manualId=item.manual_id,
                    manualTitle=item.manual_title,
                    versionId=item.version_id,
                    versionLabel=item.version_label,
                    heading=item.heading,
                    pageStart=item.page_start,
                    pageEnd=item.page_end,
                    detailUrl=item.detail_url,
                )
            )

            if len(citations) >= 3:
                break

        return citations

    def _is_procedure_question(self, query: str, language: str) -> bool:
        lowered = query.lower()
        hints = PROCEDURE_HINTS.get(language, PROCEDURE_HINTS["en"])
        return any(hint in lowered for hint in hints)

    def _intent_tokens(self, query: str) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()

        for raw_token in re.findall(r"[\w가-힣áéíóúñü]+", query.lower()):
            token = self._normalize_token(raw_token)
            if not token or token in seen:
                continue
            seen.add(token)
            tokens.append(token)

            for expanded in INTENT_EXPANSIONS.get(token, set()):
                normalized = self._normalize_token(expanded)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                tokens.append(normalized)

        return tokens

    def _select_primary_evidence(
        self,
        results: list[SearchResultItem],
        intent_tokens: list[str],
    ) -> list[SearchResultItem]:
        if not results:
            return []

        primary_version_id = results[0].version_id
        same_version = [item for item in results if item.version_id == primary_version_id]
        relevant_same_version = [
            item for item in same_version if self._result_intent_score(item, intent_tokens) > 0
        ]
        if relevant_same_version:
            return sorted(
                relevant_same_version,
                key=lambda item: (-self._actionable_result_score(item), item.page_start, item.page_end, -item.score),
            )

        relevant = [item for item in results if self._result_intent_score(item, intent_tokens) > 0]
        if relevant:
            return sorted(
                relevant,
                key=lambda item: (-self._actionable_result_score(item), -item.score, item.page_start, item.page_end),
            )

        return [results[0]]

    def _result_intent_score(self, item: SearchResultItem, intent_tokens: list[str]) -> float:
        if not intent_tokens:
            return item.score

        haystack = self._normalize_token(f"{item.heading} {item.snippet} {' '.join(item.tags)}")
        score = 0.0
        for token in intent_tokens:
            if token and token in haystack:
                score += 1.0
        return score

    def _build_procedure_answer(
        self,
        *,
        db: Session,
        query: str,
        language: str,
        primary_results: list[SearchResultItem],
        secondary: list[SearchResultItem],
    ) -> str | None:
        intent_tokens = self._intent_tokens(query)
        steps = self._procedure_steps(db, primary_results, language, intent_tokens)
        if not steps:
            return None

        if language == "ko":
            subject = self._procedure_subject(query) or "이 작업"
            lines = [self._build_ko_procedure_summary(subject, steps)]
            lines.extend(self._procedure_detail_lines(steps[2:], language))
            return "\n".join(lines)

        if language == "es":
            lines = ["Siga estos pasos."]
            lines.extend(self._procedure_detail_lines(steps, language))
            return "\n".join(lines)

        lines = ["Follow these steps."]
        lines.extend(self._procedure_detail_lines(steps, language))
        return "\n".join(lines)

    def _procedure_steps(
        self,
        db: Session,
        results: list[SearchResultItem],
        language: str,
        intent_tokens: list[str],
    ) -> list[str]:
        steps: list[str] = []
        seen: set[str] = set()
        prioritized_results = self._prioritize_procedure_results(results, intent_tokens)

        for item in prioritized_results[:3]:
            for snippet in self._candidate_sentences_for_language(item, language):
                cleaned = self._clean_step_text(snippet, heading=item.heading, language=language)
                if not cleaned:
                    continue
                normalized = self._normalize_token(cleaned)
                if normalized in seen:
                    continue
                seen.add(normalized)
                steps.append(cleaned)
                if len(steps) >= 4:
                    return self._prioritize_procedure_step_texts(steps, intent_tokens)

        for snippet in self._page_context_sentences(
            db,
            prioritized_results[:1],
            language,
            intent_tokens,
        ):
            cleaned = self._clean_step_text(snippet, heading=prioritized_results[0].heading, language=language)
            if not cleaned:
                continue
            normalized = self._normalize_token(cleaned)
            if normalized in seen:
                continue
            seen.add(normalized)
            steps.append(cleaned)
            if len(steps) >= 4:
                return self._prioritize_procedure_step_texts(steps, intent_tokens)

        return self._prioritize_procedure_step_texts(steps, intent_tokens)

    def _page_context_sentences(
        self,
        db: Session,
        results: list[SearchResultItem],
        language: str,
        intent_tokens: list[str],
    ) -> list[str]:
        if not results:
            return []

        version_id = results[0].version_id
        pages: set[int] = set()
        for item in results[:3]:
            if item.version_id != version_id:
                continue
            pages.update(range(max(1, item.page_start), item.page_end + 1))

        if not pages:
            return []

        min_page = max(1, min(pages))
        max_page = max(pages) + 1
        rows = db.scalars(
            select(SourcePage)
            .where(SourcePage.manual_version_id == version_id)
            .where(SourcePage.page_number >= min_page)
            .where(SourcePage.page_number <= max_page)
            .order_by(SourcePage.page_number.asc())
        ).all()

        sentences: list[str] = []
        for row in rows:
            text = re.sub(r"[\x00-\x1f\x7f]", " ", row.extracted_text or "")
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                continue
            parts = [
                part.strip(" .")
                for part in re.split(r"(?<=[.!?])\s+|(?=💡)", text)
                if part.strip()
            ]
            for part in parts:
                if language == "ko" and not re.search(r"[가-힣]", part):
                    continue
                normalized = self._normalize_token(part)
                if not normalized:
                    continue
                if intent_tokens and not any(token in normalized for token in intent_tokens if token):
                    if not re.search(r"(버튼|입력|선택|누르|확인|서명|출력|완료|일치|로그인|POS)", part):
                        continue
                sentences.append(part)

        return sentences

    def _candidate_sentences_for_language(self, item: SearchResultItem, language: str) -> list[str]:
        snippet = re.sub(r"[\x00-\x1f\x7f]", " ", item.snippet)
        snippet = re.sub(r"\s+", " ", snippet).strip()
        if not snippet:
            return []

        sentences = [
            sentence.strip(" .")
            for sentence in re.split(r"(?<=[.!?])\s+|\s{2,}", snippet)
            if sentence.strip()
        ]
        if language == "ko":
            return [sentence for sentence in sentences if re.search(r"[가-힣]", sentence)]
        if language == "es":
            return [sentence for sentence in sentences if re.search(r"[áéíóúñü]|[a-z]", sentence.lower())]
        return sentences

    def _best_snippet_for_language(self, item: SearchResultItem, language: str) -> str:
        snippet = re.sub(r"[\x00-\x1f\x7f]", " ", item.snippet)
        snippet = re.sub(r"\s+", " ", snippet).strip()
        if not snippet:
            return ""

        sentences = [
            sentence.strip(" .")
            for sentence in re.split(r"(?<=[.!?])\s+|\s{2,}", snippet)
            if sentence.strip()
        ]
        if not sentences:
            return snippet

        if language == "ko":
            preferred = [sentence for sentence in sentences if re.search(r"[가-힣]", sentence)]
            return preferred[0] if preferred else sentences[0]

        if language == "es":
            preferred = [
                sentence
                for sentence in sentences
                if re.search(r"[áéíóúñü]|(?:\bde\b|\bpara\b|\bseleccione\b|\bsesión\b)", sentence.lower())
            ]
            return preferred[0] if preferred else sentences[0]

        return sentences[0]

    def _clean_step_text(self, text: str, *, heading: str, language: str) -> str:
        cleaned = re.sub(r"^[\W_]+", "", text).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\[\s*", "[", cleaned)
        cleaned = re.sub(r"\s*\]", "]", cleaned)
        cleaned = re.sub(r"\s+,", ",", cleaned)
        cleaned = self._trim_to_action_clause(cleaned, language)
        cleaned = self._repair_broken_korean_words(cleaned)
        if not cleaned:
            return ""
        normalized_cleaned = self._normalize_token(cleaned)
        normalized_heading = self._normalize_token(heading)
        if normalized_cleaned == normalized_heading:
            return ""
        if len(normalized_cleaned) < 8:
            return ""
        if language == "ko" and not re.search(r"(버튼|입력|선택|눌|확인|진행|표시|열리|완료|일치|로그인|접속)", cleaned):
            return ""
        return cleaned.rstrip(".") + "."

    def _trim_to_action_clause(self, text: str, language: str) -> str:
        if language != "ko":
            return text

        earliest_index: int | None = None
        for cue in KOREAN_ACTION_CUES:
            index = text.find(cue)
            if index <= 0:
                continue
            if earliest_index is None or index < earliest_index:
                earliest_index = index

        if earliest_index is not None:
            text = text[earliest_index:].strip()

        return text

    def _repair_broken_korean_words(self, text: str) -> str:
        repairs = {
            "됩 니다": "됩니다",
            "합 니다": "합니다",
            "입 니다": "입니다",
            "있 습니다": "있습니다",
            "없 습니다": "없습니다",
            "완료됩 니다": "완료됩니다",
            "관리됩 니다": "관리됩니다",
            "표시됩 니다": "표시됩니다",
            "현금 통": "현금통",
        }
        for broken, repaired in repairs.items():
            text = text.replace(broken, repaired)
        return text

    def _prioritize_procedure_results(
        self,
        results: list[SearchResultItem],
        intent_tokens: list[str],
    ) -> list[SearchResultItem]:
        if not results:
            return []

        def priority(item: SearchResultItem) -> tuple[float, int, int, float]:
            text = self._normalize_token(f"{item.heading} {item.snippet}")
            score = self._actionable_result_score(item)

            if any(token in intent_tokens for token in ("로그인", "login")):
                if "본인의아이디" in text or "로그인login" in text or "로그인해야" in text:
                    score += 3.0
                elif "로그인" in text or "login" in text:
                    score += 1.2
                if "pos선택" in text or "pagdr" in text or "pbscreen" in text:
                    score += 0.5

            if any(token in intent_tokens for token in ("마감", "마감하기", "cierre")):
                if "영업을마무리" in text or "마감정산영수증" in text or "마감하기" in text:
                    score += 1.2
                if "교대하기" in text or "교대정산영수증" in text:
                    score -= 0.6

            if any(token in intent_tokens for token in ("교대", "turno", "cambio")):
                if "교대하기" in text or "교대정산영수증" in text:
                    score += 1.0

            return (-score, item.page_start, item.page_end, -item.score)

        return sorted(results, key=priority)

    def _prioritize_procedure_step_texts(
        self,
        steps: list[str],
        intent_tokens: list[str],
    ) -> list[str]:
        if len(steps) <= 1:
            return steps

        def priority(indexed_step: tuple[int, str]) -> tuple[int, int]:
            index, step = indexed_step
            normalized = self._normalize_token(step)

            if any(token in intent_tokens for token in ("로그인", "login")):
                if "본인의아이디" in normalized or ("로그인" in normalized and "로그인후" not in normalized):
                    return (0, index)
                if "로그인후" in normalized or "pos선택" in normalized:
                    return (1, index)
                if "담당하는존" in normalized or "pagdr" in normalized or "pbscreen" in normalized:
                    return (2, index)

            if any(token in intent_tokens for token in ("마감", "마감하기", "cierre")):
                if "영업을마무리" in normalized or "마감하기" in normalized:
                    return (0, index)
                if "권종별금액" in normalized or "예상금액과일치" in normalized:
                    return (1, index)
                if "확인및서명하기" in normalized or "참여한매니저" in normalized:
                    return (2, index)
                if "영수증" in normalized or "마감이완료" in normalized:
                    return (3, index)

            return (4, index)

        return [step for _, step in sorted(enumerate(steps), key=priority)]

    def _actionable_result_score(self, item: SearchResultItem) -> float:
        score = item.score
        snippet = self._best_snippet_for_language(item, "ko")
        if re.search(r"(버튼|입력|선택|눌|확인|진행|표시|열리|완료|일치)", snippet):
            score += 1.0
        if len(self._normalize_token(snippet)) >= 12:
            score += 0.4
        if re.match(r"^\d+(\.\d+)*$", item.heading.strip()):
            score -= 0.3
        return score

    def _normalize_token(self, text: str) -> str:
        normalized = re.sub(r"[\x00-\x1f\x7f]", " ", text.lower())
        normalized = re.sub(r"[^\w\s가-힣áéíóúñü]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        compact = normalized.replace(" ", "")

        for particle in KOREAN_QUERY_PARTICLES:
            if len(compact) > len(particle) + 1 and compact.endswith(particle):
                compact = compact[: -len(particle)]
                break

        if compact in QUERY_STOPWORDS:
            return ""

        return compact

    def _procedure_subject(self, query: str) -> str:
        cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", query).strip()
        cleaned = re.sub(r"[?!.]+$", "", cleaned).strip()
        cleaned = re.split(r"(어떻게|방법|절차|순서|하나요|할까요|하려면|할때|때는)", cleaned, maxsplit=1)[0].strip()
        cleaned = re.sub(r"(은|는|을|를|이|가)$", "", cleaned).strip()
        return cleaned

    def _build_ko_procedure_summary(self, subject: str, steps: list[str]) -> str:
        first = self._to_ko_summary_clause(steps[0])
        first_sentence = f"{subject}{self._topic_particle(subject)} {first}"
        if not first_sentence.endswith("."):
            first_sentence += "."

        if len(steps) > 1:
            first_normalized = self._normalize_token(steps[0])
            second_normalized = self._normalize_token(steps[1])
            if (
                first_normalized == second_normalized
                or first_normalized in second_normalized
                or second_normalized in first_normalized
            ):
                return first_sentence
            second = self._to_ko_followup_clause(steps[1])
            if second:
                return f"{first_sentence}\n{second}"

        return first_sentence

    def _to_ko_summary_clause(self, text: str) -> str:
        clause = text.rstrip(".")
        clause = clause.replace("때는", "때")
        clause = clause.replace("버튼을 누릅니다", "버튼을 누르면 됩니다")
        clause = clause.replace("들어갈 수 있습니다", "들어가면 됩니다")
        clause = clause.replace("확인할 수 있습니다", "확인하면 됩니다")
        clause = clause.replace("선택합니다", "선택하면 됩니다")
        return clause

    def _to_ko_followup_clause(self, text: str) -> str:
        clause = text.rstrip(".")
        clause = re.sub(r"^그러면\s*", "이후 ", clause)
        clause = re.sub(r"^먼저\s*", "", clause)
        return clause + "."

    def _procedure_detail_lines(self, steps: list[str], language: str) -> list[str]:
        if language == "ko":
            return [self._to_ko_followup_clause(step) for step in steps[:3]]
        return steps[:3]

    def _topic_particle(self, subject: str) -> str:
        trimmed = subject.strip()
        if not trimmed:
            return "는"

        last = trimmed[-1]
        if "가" <= last <= "힣":
            return "은" if (ord(last) - ord("가")) % 28 else "는"

        if re.search(r"[bcdfghjklmnpqrstvwxyz]$", trimmed.lower()):
            return "은"

        return "는"

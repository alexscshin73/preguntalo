import json
import re
from collections import Counter

from app.core.security import slugify
from app.services.text import normalize_text


STOPWORDS = {
    "and",
    "are",
    "como",
    "con",
    "del",
    "donde",
    "esta",
    "este",
    "for",
    "from",
    "how",
    "into",
    "los",
    "manual",
    "manuales",
    "para",
    "por",
    "que",
    "the",
    "this",
    "una",
    "user",
    "users",
    "when",
    "where",
    "with",
    "관련",
    "관리자",
    "매뉴얼",
    "방법",
    "문의",
    "사용자",
    "서비스",
    "안될",
    "어떻게",
    "언어",
    "알려줘",
    "전체",
    "절차",
    "질문",
    "페이지",
    "확인",
    "화면",
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
    "될까",
    "되는",
    "됩니다",
    "되나요",
    "있나요",
    "없나요",
    "주세요",
]


class TagService:
    def extract_tags(self, *parts: str, limit: int = 8) -> list[str]:
        counter: Counter[str] = Counter()

        for part in parts:
            normalized = normalize_text(part)
            part_tokens: list[str] = []
            for token in re.findall(r"[\w가-힣áéíóúñü]+", normalized):
                clean = self._normalize_token(token)
                if not self.is_valid_tag(clean):
                    continue

                slug = slugify(clean).replace("-", "")
                if len(slug) < 2:
                    continue

                counter[clean] += 1
                part_tokens.append(clean)

            for left, right in zip(part_tokens, part_tokens[1:], strict=False):
                compound = self.normalize_tag(f"{left}{right}")
                if not self.is_valid_tag(compound):
                    continue
                counter[compound] += 2

        return [tag for tag, _ in counter.most_common(limit)]

    def merge_tags(self, *tag_groups: list[str], limit: int = 12) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()

        for group in tag_groups:
            for tag in group:
                normalized = self.normalize_tag(tag)
                if not normalized or normalized in seen:
                    continue
                merged.append(normalized)
                seen.add(normalized)
                if len(merged) >= limit:
                    return merged

        return merged

    def normalize_tag(self, tag: str) -> str:
        cleaned = normalize_text(tag).replace(" ", "")
        return cleaned[:32] if cleaned else ""

    def is_valid_tag(self, tag: str) -> bool:
        if len(tag) < 2 or tag.isdigit() or tag in STOPWORDS:
            return False

        if re.search(r"[가-힣]", tag) and any(tag.endswith(ending) for ending in KOREAN_VERB_ENDINGS):
            return False

        return True

    def dump_tags(self, tags: list[str]) -> str:
        normalized = self.merge_tags(tags)
        return json.dumps(normalized, ensure_ascii=False)

    def load_tags(self, raw_tags: str | None) -> list[str]:
        if not raw_tags:
            return []

        try:
            parsed = json.loads(raw_tags)
        except json.JSONDecodeError:
            return []

        if not isinstance(parsed, list):
            return []

        return self.merge_tags([str(tag) for tag in parsed])

    def format_hashtag(self, tag: str) -> str:
        normalized = self.normalize_tag(tag)
        return f"#{normalized}" if normalized else "#"

    def _normalize_token(self, token: str) -> str:
        clean = token.strip().lower()

        for particle in KOREAN_PARTICLES:
            if len(clean) > len(particle) + 1 and clean.endswith(particle):
                clean = clean[: -len(particle)]
                break

        return clean

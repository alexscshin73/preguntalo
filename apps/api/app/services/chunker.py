import re

from app.services.parser import ParsedLine


class ChunkCandidate:
    def __init__(self, text: str, page_start: int, page_end: int) -> None:
        self.text = text
        self.page_start = page_start
        self.page_end = page_end


class Chunker:
    def split(self, lines: list[ParsedLine], max_chars: int = 700) -> list[ChunkCandidate]:
        if not lines:
            return []

        chunks: list[ChunkCandidate] = []
        current_lines: list[ParsedLine] = []
        current_length = 0
        current_start = lines[0].page_number
        current_end = current_start

        def flush() -> None:
            nonlocal current_lines, current_length, current_start, current_end
            if not current_lines:
                return
            text = "\n".join(line.text for line in current_lines).strip()
            if text:
                chunks.append(ChunkCandidate(text=text, page_start=current_start, page_end=current_end))
            current_lines = []
            current_length = 0

        for line in lines:
            if current_lines:
                should_flush = (
                    line.role == "heading"
                    or line.role == "caption"
                    or line.role == "ocr_hint"
                    or current_length + len(line.text) + 1 > max_chars
                    or line.page_number != current_end
                )
                if should_flush:
                    flush()
                    current_start = line.page_number
                    current_end = line.page_number
            else:
                current_start = line.page_number
                current_end = line.page_number

            current_lines.append(line)
            current_length += len(line.text) + 1
            current_end = line.page_number

        flush()
        return chunks

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(re.findall(r"\S+", text)))

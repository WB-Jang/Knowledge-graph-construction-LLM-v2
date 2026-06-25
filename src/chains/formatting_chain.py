"""Formatter chain: normalizes raw legal text into Markdown using a small/fast LLM.

The formatter (mistral-nemo) converts PDF-extracted text into a structured
Markdown format where each article begins with a '## 제N조' heading. This makes
downstream regex splitting deterministic and reliable.

Long documents are split into chunks before formatting so that a small model
is never asked to echo back tens of thousands of characters in a single call
(which causes truncation / near-empty responses). Each chunk is formatted
independently and the results are concatenated.

Safety: if a chunk's output is shorter than 80% of that chunk's input, the raw
chunk is kept unchanged to avoid silently dropping content.

Debug: set FORMATTER_DEBUG=true to print a preview of each chunk's raw LLM
output (useful for diagnosing refusals / empty responses).
"""
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm.llm_client import get_formatter_llm

FORMATTER_SYSTEM = """당신은 한국 법령 문서 전문 포맷터입니다.
입력된 법령 원문 텍스트를 정확히 아래 Markdown 형식으로 변환하세요.

규칙:
1. 각 조항(제N조)은 반드시 '## 제N조' 형식의 헤딩으로 시작합니다.
2. 장(章)과 절(節) 제목은 '# 제N장 제목' 또는 '### 제N절 제목' 형식으로 표기합니다.
3. 부칙은 '## 부칙' 헤딩으로 표기합니다.
4. 각 항(項)은 별도 줄에 유지합니다. 호(號)는 들여쓰기 없이 번호를 유지합니다.
5. 원문 내용을 생략하거나 요약하지 마세요. 모든 텍스트를 보존하세요.
6. 출력은 변환된 Markdown만 포함해야 합니다. 설명이나 주석을 추가하지 마세요.
"""

FORMATTER_HUMAN = """다음 법령 텍스트를 Markdown 형식으로 변환하세요:

{text}"""

# 청크당 최대 입력 문자 수
FORMATTER_CHUNK_SIZE = int(os.getenv("FORMATTER_CHUNK_SIZE", "8000"))
FORMATTER_DEBUG = os.getenv("FORMATTER_DEBUG", "false").lower() == "true"
# 출력 길이 안전 범위 (입력 대비 비율). 하한 미만=절삭, 상한 초과=반복/환각으로 간주
FORMATTER_MIN_RATIO = float(os.getenv("FORMATTER_MIN_RATIO", "0.8"))
FORMATTER_MAX_RATIO = float(os.getenv("FORMATTER_MAX_RATIO", "1.3"))


def _split_into_chunks(text: str, chunk_size: int) -> list:
    """Split text into chunks of ~chunk_size chars.

    Strategy:
    1. Try to break on double-newlines (paragraph boundaries).
    2. If no double-newlines exist (common in raw PDF text), fall back to
       single-newline boundaries.
    3. If even that produces a single giant block, fall back to hard char splits
       so very long documents are always processed in manageable pieces.
    """
    # 우선순위: \n\n > \n > 문자 단위
    if "\n\n" in text:
        sep = "\n\n"
    elif "\n" in text:
        sep = "\n"
    else:
        sep = None

    if sep:
        lines = text.split(sep)
    else:
        lines = [text]

    chunks: list = []
    buf: list = []
    buf_len = 0
    sep_len = len(sep) if sep else 0

    for line in lines:
        line_len = len(line) + sep_len
        # 단일 라인이 청크 한도보다 크면 독립 청크로 둠 (잘리지 않도록)
        if buf and buf_len + line_len > chunk_size:
            chunks.append((sep or "").join(buf))
            buf, buf_len = [], 0
        buf.append(line)
        buf_len += line_len

    if buf:
        chunks.append((sep or "").join(buf))

    # 분할이 안 됐고 여전히 한 덩어리가 한도보다 크면 문자 단위 강제 분할
    if len(chunks) == 1 and len(chunks[0]) > chunk_size:
        raw = chunks[0]
        chunks = [raw[i:i + chunk_size] for i in range(0, len(raw), chunk_size)]

    return chunks


class FormattingChain:
    """LLM-based Markdown normalizer for Korean legal texts."""

    def __init__(self):
        self.llm = get_formatter_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", FORMATTER_SYSTEM),
            ("human", FORMATTER_HUMAN),
        ])
        self.chain = prompt | self.llm | StrOutputParser()

    def _format_chunk(self, text: str, idx: int, total: int) -> str:
        """Format a single chunk; fall back to raw text if it looks truncated."""
        print(f"  🧩 [formatter] chunk {idx}/{total} 포맷팅 요청 중... ({len(text)}자)")
        try:
            result = self.chain.invoke({"text": text}).strip()
        except Exception as e:
            print(f"⚠️  [formatter] chunk {idx}/{total} LLM 호출 실패 ({e}); 원문 사용")
            return text

        # 실패(너무 짧음)시 실제 출력 내용을 항상 표시 (원인 파악용)
        if len(result) < len(text) * FORMATTER_MIN_RATIO:
            preview = result[:500].replace("\n", "\\n")
            print(f"⚠️  [formatter] chunk {idx}/{total} 출력이 너무 짧음 "
                  f"({len(result)} vs {len(text)} chars); 해당 청크는 원문 사용")
            print(f"🔎 [formatter] chunk {idx} LLM 실제 출력: {preview!r}")
            return text

        # 출력이 비정상적으로 김(반복/환각): 원문 사용으로 중복 노드 생성 방지
        if len(result) > len(text) * FORMATTER_MAX_RATIO:
            tail = result[-500:].replace("\n", "\\n")
            print(f"⚠️  [formatter] chunk {idx}/{total} 출력이 비정상적으로 김 "
                  f"({len(result)} vs {len(text)} chars, "
                  f"비율 {len(result)/max(len(text),1):.2f}x); 반복/환각 의심 → 원문 사용")
            print(f"🔎 [formatter] chunk {idx} 출력 끝부분: {tail!r}")
            return text

        if FORMATTER_DEBUG:
            preview = result[:300].replace("\n", "\\n")
            print(f"🔎 [formatter-debug] chunk {idx}/{total} "
                  f"in={len(text)} out={len(result)} chars")
            print(f"🔎 [formatter-debug] chunk {idx} 출력 미리보기: {preview!r}")

        return result

    def format(self, text: str) -> str:
        """Normalize text to Markdown, chunking long inputs.

        Each chunk falls back to its raw text on failure, so partial formatting
        is preserved instead of discarding the whole document.
        """
        chunks = _split_into_chunks(text, FORMATTER_CHUNK_SIZE)
        if len(chunks) > 1:
            print(f"🧩 [formatter] 입력 {len(text)}자를 {len(chunks)}개 청크로 분할 "
                  f"(청크당 ~{FORMATTER_CHUNK_SIZE}자)")
        else:
            print(f"🧩 [formatter] 입력 {len(text)}자, 청크 1개로 처리")

        formatted_parts = [
            self._format_chunk(chunk, i + 1, len(chunks))
            for i, chunk in enumerate(chunks)
        ]

        sep = "\n\n" if "\n\n" in text else "\n"
        combined = sep.join(formatted_parts).strip()

        # 전체가 비정상적으로 짧으면 최종 안전망으로 원문 반환
        if len(combined) < len(text) * 0.8:
            print(f"⚠️  [formatter] 전체 출력이 너무 짧음 "
                  f"({len(combined)} vs {len(text)} chars); 원문 전체 사용")
            return text
        return combined

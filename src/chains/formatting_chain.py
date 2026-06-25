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

# 청크당 최대 입력 문자 수 (작은 모델이 안정적으로 처리할 수 있는 크기)
FORMATTER_CHUNK_SIZE = int(os.getenv("FORMATTER_CHUNK_SIZE", "8000"))
FORMATTER_DEBUG = os.getenv("FORMATTER_DEBUG", "false").lower() == "true"


def _split_into_chunks(text: str, chunk_size: int) -> list:
    """Split text into chunks of ~chunk_size chars, breaking on paragraph
    boundaries (blank lines) so that articles are not cut mid-sentence."""
    paragraphs = text.split("\n\n")
    chunks: list = []
    buf: list = []
    buf_len = 0
    for para in paragraphs:
        para_len = len(para) + 2  # account for the "\n\n" separator
        # 단일 문단이 청크 한도보다 크면 그대로 독립 청크로 둠
        if buf and buf_len + para_len > chunk_size:
            chunks.append("\n\n".join(buf))
            buf, buf_len = [], 0
        buf.append(para)
        buf_len += para_len
    if buf:
        chunks.append("\n\n".join(buf))
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
        try:
            result = self.chain.invoke({"text": text}).strip()
        except Exception as e:
            print(f"⚠️  [formatter] chunk {idx}/{total} LLM 호출 실패 ({e}); 원문 사용")
            return text

        if FORMATTER_DEBUG:
            preview = result[:300].replace("\n", "\\n")
            print(f"🔎 [formatter-debug] chunk {idx}/{total} "
                  f"in={len(text)} out={len(result)} chars")
            print(f"🔎 [formatter-debug] chunk {idx} 출력 미리보기: {preview!r}")

        # Safety: reject if the model truncated this chunk (< 80% char count)
        if len(result) < len(text) * 0.8:
            print(f"⚠️  [formatter] chunk {idx}/{total} 출력이 너무 짧음 "
                  f"({len(result)} vs {len(text)} chars); 해당 청크는 원문 사용")
            return text
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

        formatted_parts = [
            self._format_chunk(chunk, i + 1, len(chunks))
            for i, chunk in enumerate(chunks)
        ]
        combined = "\n\n".join(formatted_parts).strip()

        # 전체가 비정상적으로 짧으면(모든 청크 실패) 최종 안전망으로 원문 반환
        if len(combined) < len(text) * 0.8:
            print(f"⚠️  [formatter] 전체 출력이 너무 짧음 "
                  f"({len(combined)} vs {len(text)} chars); 원문 전체 사용")
            return text
        return combined

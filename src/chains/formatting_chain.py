"""Formatter chain: TEXT NORMALIZATION of PDF-extracted Korean legal text.

역할(중요): 이 체인은 '구조 표시(## 제N조 등)'를 하지 않는다. 조/항/호 구조
분할은 결정론적 계층 파서(utils.text_processor.split_into_units)가 담당한다.
포맷터 LLM의 역할은 오직 '텍스트 정규화'다:
  - PDF 추출 과정에서 한 문장이 여러 줄로 깨진 것을 다시 잇기
  - 페이지 머리말/꼬리말, 쪽번호 등 잡음 제거
  - 항 마커(①②③)가 (1)/1 등으로 훼손된 경우 원문자(①②③)로 복원
구조를 새로 만들거나 내용을 요약/삭제하지 않는다.

긴 문서는 청크로 나눠 정규화한다(작은 모델이 한 번에 수만 자를 처리하다
절삭/반복하는 것을 방지). 청크별로 길이 비율이 안전 범위를 벗어나면(절삭 또는
반복/환각) 해당 청크는 원문을 그대로 사용한다.

Debug: FORMATTER_DEBUG=true 로 청크별 LLM 원본 출력 미리보기를 출력.
"""
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm.llm_client import get_formatter_llm

FORMATTER_SYSTEM = """당신은 한국 법령 원문을 정리(정규화)하는 전문가입니다.
PDF에서 추출되어 줄바꿈·잡음이 섞인 법령 텍스트를 깨끗한 원문으로 복원하세요.

규칙:
1. 구조 표시(##, #, 마크다운 헤딩, 번호 재부여)를 하지 마세요. 조/항 구조는
   별도 시스템이 처리합니다.
2. PDF 추출로 인해 한 문장이 여러 줄로 잘린 경우, 자연스러운 문장으로 다시 이으세요.
3. 페이지 번호, 머리말/꼬리말, 반복되는 법령명 헤더 등 본문이 아닌 잡음을 제거하세요.
4. 항 번호가 (1),(2) 또는 1,2 등으로 훼손되었으면 원문자 ①②③…로 복원하세요.
5. 조문 번호(제N조), 항(①②③), 호(1. 2.), 목(가. 나.)의 텍스트는 절대 변경/삭제하지 마세요.
6. 내용을 요약·생략·창작하지 마세요. 모든 조문 내용을 그대로 보존하세요.
7. 출력은 정리된 법령 본문 텍스트만 포함합니다. 설명·주석을 붙이지 마세요.
"""

FORMATTER_HUMAN = """다음 법령 텍스트를 위 규칙에 따라 정리(정규화)하세요:

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

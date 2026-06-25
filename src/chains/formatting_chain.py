"""Formatter chain: normalizes raw legal text into Markdown using a small/fast LLM.

The formatter (mistral-nemo) converts PDF-extracted text into a structured
Markdown format where each article begins with a '## 제N조' heading. This makes
downstream regex splitting deterministic and reliable.

Safety: if the LLM output is shorter than 80% of the input, the raw input is
returned unchanged to avoid truncation bugs.
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


class FormattingChain:
    """LLM-based Markdown normalizer for Korean legal texts."""

    def __init__(self):
        self.llm = get_formatter_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", FORMATTER_SYSTEM),
            ("human", FORMATTER_HUMAN),
        ])
        self.chain = prompt | self.llm | StrOutputParser()

    def format(self, text: str) -> str:
        """Normalize text to Markdown. Falls back to raw text if output is too short."""
        try:
            result = self.chain.invoke({"text": text})
            # Safety: reject if LLM truncated (< 80% character count)
            if len(result.strip()) < len(text) * 0.8:
                print(f"⚠️  Formatter output too short ({len(result)} vs {len(text)} chars); using raw text")
                return text
            return result.strip()
        except Exception as e:
            print(f"⚠️  Formatter LLM failed ({e}); using raw text")
            return text

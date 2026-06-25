"""Evaluator chain: LLM-as-a-Judge for article-level graph quality.

Uses deepseek-v4-flash (EVALUATOR_MODEL) to assess whether the extracted
nodes and triplets for a given article are complete and faithful to the source.

Returns a structured EvaluationResult with:
  - passed: bool       (True = PASS, False = FAIL → triggers re-generation)
  - score: float       (0.0–1.0)
  - reason: str        (brief explanation for the verdict)
  - feedback: str      (specific improvement instructions for the Generator)
"""
import json
import os
import re
from typing import List, Optional
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from models.schemas import LegalEntity, GraphTriplet
from llm.llm_client import get_evaluator_llm

PASS_THRESHOLD = float(os.getenv("EVAL_PASS_THRESHOLD", "0.7"))

EVALUATOR_SYSTEM = """당신은 한국 법률 지식 그래프 품질 평가 전문가입니다.
주어진 법령 조항의 원문(Source)과 추출된 노드(Node) 및 관계 트리플(Triplet)을 비교하여
그래프 데이터의 완전성(Completeness)과 충실성(Faithfulness)을 평가하세요.

평가 기준:
1. 완전성(Completeness, 0~5점): 원문의 핵심 의무, 권한, 정의, 제재가 트리플로 빠짐없이 추출되었는가?
2. 충실성(Faithfulness, 0~5점): 추출된 주체/관계/대상이 원문을 왜곡하거나 확대 해석하지 않는가?

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "completeness": <0-5 정수>,
  "faithfulness": <0-5 정수>,
  "verdict": "PASS" 또는 "FAIL",
  "reason": "<판정 이유 1-2문장>",
  "feedback": "<Generator에게 보내는 구체적인 개선 지시사항. PASS이면 'None'>"
}}"""

EVALUATOR_HUMAN = """[원문 조항]
{full_text}

[추출된 노드]
- 조항번호: {article_number}
- 개념: {concept}
- 주체: {subject}
- 행위: {action}
- 대상: {object}
- 강제성: {legal_force}

[추출된 트리플]
{triplets_str}

위 추출 결과를 평가하고 JSON으로 응답하세요."""


class EvaluationResult(BaseModel):
    completeness: int = Field(ge=0, le=5)
    faithfulness: int = Field(ge=0, le=5)
    verdict: str
    reason: str
    feedback: str
    score: float = 0.0

    def model_post_init(self, __context):
        self.score = (self.completeness + self.faithfulness) / 10.0

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS" and self.score >= PASS_THRESHOLD


def _format_triplets(triplets: List[GraphTriplet]) -> str:
    if not triplets:
        return "(없음)"
    lines = []
    for t in triplets:
        lines.append(f"  [{t.article_number}] {t.subject} --[{t.relation}]--> {t.object} (conf={t.confidence:.2f})")
    return "\n".join(lines)


class EvaluatorChain:
    """Article-level LLM evaluator using deepseek-v4-flash."""

    def __init__(self):
        self.llm = get_evaluator_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", EVALUATOR_SYSTEM),
            ("human", EVALUATOR_HUMAN),
        ])
        self.chain = prompt | self.llm | StrOutputParser()

    def evaluate(
        self,
        entity: LegalEntity,
        triplets: List[GraphTriplet],
    ) -> EvaluationResult:
        """Evaluate one article's extracted graph data. Returns EvaluationResult."""
        triplets_str = _format_triplets(triplets)
        try:
            raw = self.chain.invoke({
                "full_text": entity.full_text,
                "article_number": entity.article_number,
                "concept": entity.concept or "N/A",
                "subject": entity.subject or "N/A",
                "action": entity.action or "N/A",
                "object": entity.object or "N/A",
                "legal_force": entity.legal_force or "N/A",
                "triplets_str": triplets_str,
            })
            # Extract JSON from the response (may be wrapped in markdown code fences)
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not json_match:
                raise ValueError(f"No JSON found in evaluator response: {raw[:200]}")
            data = json.loads(json_match.group())
            return EvaluationResult(**data)
        except Exception as e:
            print(f"⚠️  Evaluator failed for {entity.article_number}: {e}")
            # Conservative fallback: FAIL so the article gets a retry chance
            return EvaluationResult(
                completeness=0,
                faithfulness=0,
                verdict="FAIL",
                reason=f"Evaluator error: {e}",
                feedback="Re-extract the article from scratch. Ensure all obligations, rights, and definitions are captured as triplets.",
            )

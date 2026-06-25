"""Legal Knowledge Graph workflow — Pipeline v2.

Architecture (per article):
  format_text → split_articles → for each article:
    extract_entity → extract_relations → rule_validate
    → llm_evaluate → [PASS → collect] | [FAIL → reflect & retry (max 3×) → DLQ]
  → validate_graph (global dedup)
"""
import csv
import os
import re
from datetime import datetime
from typing import List, TypedDict, Optional, Dict

from langgraph.graph import StateGraph, END

from models.schemas import LegalEntity, GraphTriplet, LegalDocument
from chains.formatting_chain import FormattingChain
from chains.entity_extraction_chain import EntityExtractionChain
from chains.relation_extraction_chain import RelationExtractionChain
from chains.evaluator_chain import EvaluatorChain, EvaluationResult
from validators.rule_validator import validate_article_triplets
from utils.text_processor import split_markdown_articles, split_and_categorize_articles

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
# 의미 유사도 기반 동적 글로벌 컨텍스트 (옵션, 기본 비활성화)
ENABLE_SEMANTIC_GLOBAL_CONTEXT = os.getenv("ENABLE_SEMANTIC_GLOBAL_CONTEXT", "false").lower() == "true"
DLQ_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "output", "dead_letter_queue.csv"
)


class GraphState(TypedDict):
    raw_text: str
    formatted_text: str
    categorized_text: dict
    entities: List[LegalEntity]
    global_entities: List[LegalEntity]
    triplets: List[GraphTriplet]
    document: LegalDocument
    current_index: int
    errors: List[str]


def _append_dlq(article_number: str, full_text: str, reason: str, feedback: str):
    """Append a failed article to the Dead Letter Queue CSV."""
    os.makedirs(os.path.dirname(DLQ_PATH), exist_ok=True)
    write_header = not os.path.exists(DLQ_PATH)
    with open(DLQ_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "article_number", "reason", "feedback", "full_text"])
        if write_header:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().isoformat(),
            "article_number": article_number,
            "reason": reason,
            "feedback": feedback,
            "full_text": full_text.replace("\n", " "),
        })


class LegalKnowledgeGraphWorkflow:
    """법률 지식 그래프 생성 워크플로우 (v2)"""

    def __init__(self):
        self.formatter = FormattingChain()
        self.entity_chain = EntityExtractionChain()
        self.relation_chain = RelationExtractionChain()
        self.evaluator = EvaluatorChain()
        self.pipeline_version = os.getenv("PIPELINE_VERSION", "2.0")
        self.generator_model = os.getenv("GENERATOR_MODEL", "google/gemma-4-26b-a4b-it")
        self.evaluator_model = os.getenv("EVALUATOR_MODEL", "deepseek/deepseek-v4-flash")

        # 옵션: 의미 유사도 기반 동적 글로벌 컨텍스트 선택기 (기본 비활성화)
        self.semantic_selector = None
        if ENABLE_SEMANTIC_GLOBAL_CONTEXT:
            from utils.semantic_context import SemanticContextSelector
            self.semantic_selector = SemanticContextSelector()
            print(f"🧭 의미 유사도 글로벌 컨텍스트 활성화 (method={self.semantic_selector.method}, "
                  f"top_k={self.semantic_selector.top_k})")

        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(GraphState)

        workflow.add_node("format_text", self._format_text)
        workflow.add_node("split_articles", self._split_articles)
        workflow.add_node("extract_entities", self._extract_entities)
        workflow.add_node("extract_relations", self._extract_relations)
        workflow.add_node("validate_graph", self._validate_graph)

        workflow.set_entry_point("format_text")
        workflow.add_edge("format_text", "split_articles")
        workflow.add_edge("split_articles", "extract_entities")
        workflow.add_edge("extract_entities", "extract_relations")
        workflow.add_edge("extract_relations", "validate_graph")
        workflow.add_edge("validate_graph", END)

        return workflow.compile()

    # ── Step 0 ───────────────────────────────────────────────────────────────
    def _format_text(self, state: GraphState) -> GraphState:
        print("\n[1/5] 📝 Markdown 포맷팅 중...")
        state["formatted_text"] = self.formatter.format(state["raw_text"])
        print(f"[1/5] ✅ 포맷팅 완료 ({len(state['formatted_text'])}자)")
        return state

    # ── Step 1 ───────────────────────────────────────────────────────────────
    def _split_articles(self, state: GraphState) -> GraphState:
        print("\n[2/5] ✂️  조항 분할 중...")
        text = state["formatted_text"]
        result = split_markdown_articles(text)
        md_count = len(result["main_raw"])

        # 완전성(Completeness) 가드:
        # 포맷터가 일부 청크만 마크다운으로 변환하고 나머지는 원문으로 폴백하면,
        # split_markdown_articles는 '## 제N조' 헤딩이 있는 조항만 잡아 나머지를
        # 통째로 누락한다. 따라서 '원문' 기준 정규식 파서와 개수를 비교해,
        # 마크다운이 유의미하게 적게 잡으면 정규식 결과(원문 전체)로 대체한다.
        legacy = split_and_categorize_articles(state["raw_text"])
        regex_count = len(legacy["main_raw"])

        if md_count == 0 or regex_count > md_count:
            print(f"⚠️  Markdown 분할 {md_count}개 vs 정규식(원문) {regex_count}개 — "
                  f"누락 방지를 위해 정규식 파서 결과 사용")

            def _num_from_text(t: str) -> str:
                m = re.match(r'\s*(제\s*\d+\s*조(?:의\s*\d+)?)', t)
                return m.group(1).replace(" ", "") if m else "N/A"

            def _wrap(items, addendum=False):
                return [{"article_number": _num_from_text(t), "structural_index": [],
                         "full_text": t, "is_addendum": addendum}
                        for t in items]
            result = {
                "front_raw": _wrap(legacy["front_raw"]),
                "main_raw":  _wrap(legacy["main_raw"]),
                "back_raw":  _wrap(legacy["back_raw"], addendum=True),
            }

        state["categorized_text"] = result
        state["current_index"] = 0
        print(f"[2/5] ✅ 분할 완료 (본문 {len(result['main_raw'])}개, "
              f"전문 {len(result['front_raw'])}개, 부칙 {len(result['back_raw'])}개 조항)")
        return state

    # ── Step 2 ───────────────────────────────────────────────────────────────
    def _extract_entities(self, state: GraphState) -> GraphState:
        """Entity extraction with Generator LLM; override deterministic fields."""
        main_raw = state["categorized_text"]["main_raw"]
        entities: List[LegalEntity] = []
        total = len(main_raw)
        print(f"\n[3/5] 🔍 개체(노드) 추출 중... (총 {total}개 조항)")

        for i, entry in enumerate(main_raw, 1):
            full_text = entry["full_text"]
            parsed_number = entry.get("article_number", "")
            parsed_index = entry.get("structural_index", [])

            entity = self.entity_chain.extract(full_text)
            label = (parsed_number if parsed_number and parsed_number != "N/A"
                     else (entity.article_number or "N/A"))
            print(f"  [{i}/{total}] 🔹 {label} 개체 추출: concept='{entity.concept}'")
            if parsed_number and parsed_number != "N/A":
                entity.article_number = parsed_number
            if parsed_index:
                entity.structural_index = parsed_index
            entity.pipeline_version = self.pipeline_version
            entity.generator_model = self.generator_model
            entity.evaluator_model = self.evaluator_model

            entities.append(entity)

        front_numbers = {e.get("article_number") for e in state["categorized_text"]["front_raw"]}
        global_entities = [e for e in entities if e.article_number in front_numbers]

        state["entities"] = entities
        state["global_entities"] = global_entities
        state["document"].entities = entities
        state["document"].pipeline_version = self.pipeline_version
        state["document"].generator_model = self.generator_model
        state["document"].evaluator_model = self.evaluator_model
        print(f"[3/5] ✅ 개체 추출 완료 ({len(entities)}개, 글로벌 {len(global_entities)}개)")
        return state

    # ── Step 3 ───────────────────────────────────────────────────────────────
    def _extract_relations(self, state: GraphState) -> GraphState:
        """Relation extraction with Generator LLM + rule validation + LLM evaluation.

        Per-article reflection loop: rule_validate → llm_evaluate → regenerate if FAIL.
        After MAX_RETRIES failures the article is written to the DLQ.
        """
        all_triplets: List[GraphTriplet] = []
        entities = state["entities"]
        global_entities = state.get("global_entities", [])
        accumulated_entities: List[LegalEntity] = []  # entities accepted so far (for local context)
        total = len(entities)
        print(f"\n[4/5] 🔗 관계(엣지) 추출 + 평가 중... (총 {total}개 조항)")

        for idx, entity in enumerate(entities, 1):
            print(f"  [{idx}/{total}] 🔸 {entity.article_number or 'N/A'} 관계 추출 시작")
            local_context = accumulated_entities[-3:]

            # 정적 글로벌 컨텍스트(앞 3개 조항) + (옵션) 의미 유사도 기반 동적 컨텍스트
            effective_global = global_entities
            if self.semantic_selector is not None:
                # 후보 풀: 현재 조항을 제외한 나머지 조항 전체
                candidates = [e for e in entities if e is not entity]
                semantic_picks = self.semantic_selector.select(entity, candidates)
                # 정적 컨텍스트와 합치되 article_number 기준 중복 제거
                merged = list(global_entities)
                seen = {e.article_number for e in merged}
                for pick in semantic_picks:
                    if pick.article_number not in seen:
                        merged.append(pick)
                        seen.add(pick.article_number)
                effective_global = merged

            feedback: Optional[str] = None
            accepted = False

            for attempt in range(MAX_RETRIES + 1):
                # Extract relations (with feedback from previous failed attempt if any)
                entity_for_extract = entity
                if feedback and attempt > 0:
                    # Prepend feedback to the entity's full_text so the LLM sees it
                    import copy
                    entity_for_extract = copy.copy(entity)
                    entity_for_extract.full_text = (
                        f"[이전 평가 피드백: {feedback}]\n\n{entity.full_text}"
                    )

                raw_triplets = self.relation_chain.extract(
                    entity=entity_for_extract,
                    local_context=local_context,
                    global_context=effective_global,
                )

                # Attach metadata
                for t in raw_triplets:
                    t.pipeline_version = self.pipeline_version
                    t.generator_model = self.generator_model
                    t.evaluator_model = self.evaluator_model
                    t.retry_count = attempt

                # Rule-based validation (zero cost)
                valid_triplets, rule_errors = validate_article_triplets(entity, raw_triplets)
                if rule_errors:
                    print(f"  ❌ [rule] {entity.article_number} attempt {attempt+1}: {rule_errors}")

                # LLM evaluation (deepseek-v4-flash) — full coverage, no sampling
                eval_result: EvaluationResult = self.evaluator.evaluate(entity, valid_triplets)
                score = eval_result.score

                # Attach eval metadata to entity and triplets
                entity.eval_score = score
                entity.retry_count = attempt
                for t in valid_triplets:
                    t.eval_score = score
                    t.retry_count = attempt

                print(f"  {'✅' if eval_result.passed else '❌'} [eval] {entity.article_number} "
                      f"attempt {attempt+1}/{MAX_RETRIES+1} score={score:.2f} verdict={eval_result.verdict}")

                if eval_result.passed:
                    all_triplets.extend(valid_triplets)
                    accepted = True
                    break

                feedback = eval_result.feedback
                if attempt == MAX_RETRIES:
                    # All retries exhausted — write to DLQ
                    print(f"  ⛔ [DLQ] {entity.article_number} failed after {MAX_RETRIES+1} attempts")
                    _append_dlq(
                        article_number=entity.article_number,
                        full_text=entity.full_text,
                        reason=eval_result.reason,
                        feedback=eval_result.feedback,
                    )
                    state["errors"].append(
                        f"DLQ: {entity.article_number} — {eval_result.reason}"
                    )

            accumulated_entities.append(entity)

        state["triplets"] = all_triplets
        state["document"].triplets = all_triplets
        print(f"[4/5] ✅ 관계 추출 완료 (총 {len(all_triplets)}개 트리플)")
        return state

    # ── Step 4 ───────────────────────────────────────────────────────────────
    def _validate_graph(self, state: GraphState) -> GraphState:
        """Dedup triplets; keep highest-confidence copy of each (s,r,o) key."""
        print("\n[5/5] 🧹 그래프 중복 제거 중...")
        before = len(state["triplets"])
        unique: Dict = {}
        for triplet in state["triplets"]:
            key = (triplet.subject, triplet.relation, triplet.object)
            if key not in unique or triplet.confidence > unique[key].confidence:
                unique[key] = triplet
        state["triplets"] = list(unique.values())
        state["document"].triplets = state["triplets"]
        print(f"[5/5] ✅ 중복 제거 완료 ({before} → {len(state['triplets'])}개 트리플)")
        return state

    # ── Public entry point ───────────────────────────────────────────────────
    def process(self, document: LegalDocument) -> LegalDocument:
        initial_state: GraphState = {
            "raw_text": document.content,
            "formatted_text": "",
            "categorized_text": {},
            "entities": [],
            "global_entities": [],
            "triplets": [],
            "document": document,
            "current_index": 0,
            "errors": [],
        }

        final_state = self.workflow.invoke(initial_state)

        if final_state["errors"]:
            print(f"⚠️  Warning: {len(final_state['errors'])} errors occurred")
            for error in final_state["errors"]:
                print(f"  - {error}")

        return final_state["document"]

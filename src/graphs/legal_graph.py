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
from validators.rule_validator import validate_article_triplets, flush_unknown_relations
from utils.text_processor import split_into_units

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
        """계층적 파서(조>항)로 항 단위 추출 단위를 만든다.

        정규화된 텍스트와 원문(raw) 각각에 대해 파싱한 뒤, 더 많은 단위를 만든
        쪽을 채택한다(완전성 가드). 정규화 LLM이 항 마커를 훼손해도 원문 파싱이
        받쳐주므로 조항·항 누락을 방지한다.
        """
        print("\n[2/5] ✂️  조항·항 단위 분할 중...")

        normalized = split_into_units(state["formatted_text"])
        raw = split_into_units(state["raw_text"])

        # 더 많은 단위를 만든 쪽 채택 (누락 방지). 동률이면 정규화본 우선.
        if len(raw["main_raw"]) > len(normalized["main_raw"]):
            print(f"⚠️  정규화본 {len(normalized['main_raw'])}단위 vs 원문 "
                  f"{len(raw['main_raw'])}단위 — 누락 방지를 위해 원문 파싱 결과 사용")
            result = raw
        else:
            result = normalized

        state["categorized_text"] = result
        state["current_index"] = 0
        # 통계: 고유 조 개수와 항 단위 개수
        unique_articles = {u["article_number"] for u in result["main_raw"]}
        print(f"[2/5] ✅ 분할 완료 (조 {len(unique_articles)}개 → 항 단위 "
              f"{len(result['main_raw'])}개, 전문 {len(result['front_raw'])}개, "
              f"부칙 {len(result['back_raw'])}개)")
        return state

    # ── Step 2 ───────────────────────────────────────────────────────────────
    def _extract_entities(self, state: GraphState) -> GraphState:
        """항 단위 개체 추출. 결정론적 필드(article_number, hang_number,
        article_title, structural_index)는 파서 값으로 덮어씌운다."""
        main_raw = state["categorized_text"]["main_raw"]
        entities: List[LegalEntity] = []
        total = len(main_raw)
        print(f"\n[3/5] 🔍 개체(노드) 추출 중... (총 {total}개 항 단위)")

        for i, entry in enumerate(main_raw, 1):
            art_no = entry.get("article_number") or "N/A"
            hang_no = entry.get("hang_number")
            label = f"{art_no}" + (f" ({'①②③④⑤⑥⑦⑧⑨⑩'[hang_no-1] if hang_no and hang_no <= 10 else f'항{hang_no}'})"
                                   if hang_no else "")

            cross_refs = entry.get("cross_law_refs", [])
            law_title = state["document"].title
            entity = self.entity_chain.extract(entry["full_text"], cross_refs, law_title)
            print(f"  [{i}/{total}] 🔹 {label} 개체 추출: concept='{entity.concept}'"
                  + (f" [타법참조 {len(cross_refs)}건]" if cross_refs else ""))

            # 결정론적 파서 값으로 덮어쓰기 (LLM이 틀려도 구조는 보존)
            if art_no and art_no != "N/A":
                entity.article_number = art_no
            entity.hang_number = hang_no
            entity.article_title = entry.get("article_title")
            entity.cross_law_refs = cross_refs
            if entry.get("structural_index"):
                entity.structural_index = entry["structural_index"]
            entity.pipeline_version = self.pipeline_version
            entity.generator_model = self.generator_model
            entity.evaluator_model = self.evaluator_model

            entities.append(entity)

        # 글로벌 컨텍스트: front_raw에 속한 조 번호 집합
        front_numbers = {u["article_number"] for u in state["categorized_text"]["front_raw"]}
        global_entities = [e for e in entities if e.article_number in front_numbers]

        state["entities"] = entities
        state["global_entities"] = global_entities
        state["document"].entities = entities
        state["document"].pipeline_version = self.pipeline_version
        state["document"].generator_model = self.generator_model
        state["document"].evaluator_model = self.evaluator_model
        unique_arts = {e.article_number for e in entities}
        print(f"[3/5] ✅ 개체 추출 완료 (조 {len(unique_arts)}개 → 항 단위 {len(entities)}개, "
              f"글로벌 {len(global_entities)}개)")
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
            hang_label = (f" ({'①②③④⑤⑥⑦⑧⑨⑩'[entity.hang_number-1] if entity.hang_number and entity.hang_number <= 10 else f'항{entity.hang_number}'})"
                          if entity.hang_number else "")
            print(f"  [{idx}/{total}] 🔸 {entity.article_number or 'N/A'}{hang_label} 관계 추출 시작")
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
                    law_title=state["document"].title,
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

        # 문제 5: 세션 내 미등록 relation을 CSV로 기록 (enum 확장 검토용)
        flush_unknown_relations()

        return final_state["document"]

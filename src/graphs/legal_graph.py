import os
from typing import List, TypedDict, Optional
from langgraph.graph import StateGraph, END

from models.schemas import LegalEntity, GraphTriplet, LegalDocument
from chains.formatting_chain import FormattingChain
from chains.entity_extraction_chain import EntityExtractionChain
from chains.relation_extraction_chain import RelationExtractionChain
from utils.text_processor import split_markdown_articles, split_and_categorize_articles


class GraphState(TypedDict):
    raw_text: str
    formatted_text: str              # Markdown-normalized by Formatter LLM
    categorized_text: dict           # Parsed article dicts
    entities: List[LegalEntity]
    global_entities: List[LegalEntity]
    triplets: List[GraphTriplet]
    document: LegalDocument
    current_index: int
    errors: List[str]


class LegalKnowledgeGraphWorkflow:
    """법률 지식 그래프 생성 워크플로우 (v2)

    Pipeline:
      format_text → split_articles → extract_entities
        → extract_relations → validate_graph
    """

    def __init__(self):
        self.formatter = FormattingChain()
        self.entity_chain = EntityExtractionChain()
        self.relation_chain = RelationExtractionChain()
        self.pipeline_version = os.getenv("PIPELINE_VERSION", "2.0")
        self.generator_model = os.getenv("GENERATOR_MODEL", "google/gemma-4-26b-a4b-it")
        self.evaluator_model = os.getenv("EVALUATOR_MODEL", "deepseek/deepseek-v4-flash")
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

    # ── Step 0: LLM Markdown normalization ──────────────────────────────────
    def _format_text(self, state: GraphState) -> GraphState:
        """Normalize raw PDF text to Markdown via Formatter LLM (mistral-nemo).
        Falls back to raw text if LLM output is too short (80% threshold)."""
        state["formatted_text"] = self.formatter.format(state["raw_text"])
        return state

    # ── Step 1: Article splitting ────────────────────────────────────────────
    def _split_articles(self, state: GraphState) -> GraphState:
        """Split Markdown text into article dicts with structural_index.
        Falls back to legacy regex parser if no ## headings found."""
        text = state["formatted_text"]

        result = split_markdown_articles(text)
        # Fallback: if Markdown splitter found nothing, use legacy regex parser
        if not result["main_raw"]:
            print("⚠️  Markdown splitter found no articles; falling back to regex parser")
            legacy = split_and_categorize_articles(text)
            # Wrap plain strings as minimal dicts
            result = {
                "front_raw": [{"article_number": "N/A", "structural_index": [], "full_text": t, "is_addendum": False} for t in legacy["front_raw"]],
                "main_raw":  [{"article_number": "N/A", "structural_index": [], "full_text": t, "is_addendum": False} for t in legacy["main_raw"]],
                "back_raw":  [{"article_number": "N/A", "structural_index": [], "full_text": t, "is_addendum": True}  for t in legacy["back_raw"]],
            }

        state["categorized_text"] = result
        state["current_index"] = 0
        return state

    # ── Step 2: Entity extraction ────────────────────────────────────────────
    def _extract_entities(self, state: GraphState) -> GraphState:
        """Extract LegalEntity for each article in main_raw.
        structural_index and article_number from the parser override LLM output
        to avoid hallucination."""
        main_raw = state["categorized_text"]["main_raw"]
        entities: List[LegalEntity] = []

        for entry in main_raw:
            full_text = entry["full_text"]
            parsed_number = entry.get("article_number", "")
            parsed_index = entry.get("structural_index", [])

            entity = self.entity_chain.extract(full_text)
            # Override with deterministic parser output
            if parsed_number and parsed_number != "N/A":
                entity.article_number = parsed_number
            if parsed_index:
                entity.structural_index = parsed_index
            # Attach pipeline metadata
            entity.pipeline_version = self.pipeline_version
            entity.generator_model = self.generator_model

            entities.append(entity)

        # Identify global (front) entities by article_number
        front_numbers = {e.get("article_number") for e in state["categorized_text"]["front_raw"]}
        global_entities = [e for e in entities if e.article_number in front_numbers]

        state["entities"] = entities
        state["global_entities"] = global_entities
        state["document"].entities = entities
        state["document"].pipeline_version = self.pipeline_version
        state["document"].generator_model = self.generator_model
        state["document"].evaluator_model = self.evaluator_model
        return state

    # ── Step 3: Relation extraction ──────────────────────────────────────────
    def _extract_relations(self, state: GraphState) -> GraphState:
        """Extract GraphTriplets using sliding-window local context + global context."""
        triplets: List[GraphTriplet] = []
        entities = state["entities"]
        global_entities = state.get("global_entities", [])

        for i, entity in enumerate(entities):
            local_context = entities[max(0, i - 3):i]
            try:
                result = self.relation_chain.extract(
                    entity=entity,
                    local_context=local_context,
                    global_context=global_entities,
                )
                # Attach pipeline metadata to each triplet
                for t in result:
                    t.pipeline_version = self.pipeline_version
                    t.generator_model = self.generator_model
                    t.evaluator_model = self.evaluator_model
                triplets.extend(result)
            except Exception as e:
                state["errors"].append(f"Relation extraction error for {entity.article_number}: {e}")

        state["triplets"] = triplets
        state["document"].triplets = triplets
        return state

    # ── Step 4: Graph validation ─────────────────────────────────────────────
    def _validate_graph(self, state: GraphState) -> GraphState:
        """Deduplicate triplets; keep highest-confidence copy of each (s,r,o) key."""
        unique: dict = {}
        for triplet in state["triplets"]:
            key = (triplet.subject, triplet.relation, triplet.object)
            if key not in unique or triplet.confidence > unique[key].confidence:
                unique[key] = triplet

        state["triplets"] = list(unique.values())
        state["document"].triplets = state["triplets"]
        return state

    # ── Public entry point ───────────────────────────────────────────────────
    def process(self, document: LegalDocument) -> LegalDocument:
        """Run the full pipeline and return an enriched LegalDocument."""
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

from typing import List, TypedDict
from langgraph.graph import StateGraph, END
from models.schemas import LegalEntity, GraphTriplet, LegalDocument
from chains.entity_extraction_chain import EntityExtractionChain
from chains.relation_extraction_chain import RelationExtractionChain
from utils.text_processor import split_articles


class GraphState(TypedDict):
    """그래프 상태"""
    document: LegalDocument
    articles: List[str]
    entities: List[LegalEntity]
    triplets: List[GraphTriplet]
    current_index: int
    errors: List[str]


class LegalKnowledgeGraphWorkflow:
    """법률 지식 그래프 생성 워크플로우"""
    
    def __init__(self):
        self.entity_chain = EntityExtractionChain()
        self.relation_chain = RelationExtractionChain()
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """워크플로우 구성"""
        workflow = StateGraph(GraphState)
        
        # 노드 추가
        workflow.add_node("split_articles", self._split_articles)
        workflow.add_node("extract_entities", self._extract_entities)
        workflow.add_node("extract_relations", self._extract_relations)
        workflow.add_node("validate_graph", self._validate_graph)
        
        # 엣지 설정
        workflow.set_entry_point("split_articles")
        workflow.add_edge("split_articles", "extract_entities")
        workflow.add_edge("extract_entities", "extract_relations")
        workflow.add_edge("extract_relations", "validate_graph")
        workflow.add_edge("validate_graph", END)
        
        return workflow.compile()
    
    def _split_articles(self, state: GraphState) -> GraphState:
        """Step 1: 조항 분리"""
        articles = split_articles(state["document"].content)
        state["articles"] = articles
        state["current_index"] = 0
        return state
    
    def _extract_entities(self, state: GraphState) -> GraphState:
        """Step 2: 개체 추출"""
        try:
            entities = self.entity_chain.batch_extract(state["articles"])
            state["entities"] = entities
            state["document"].entities = entities
        except Exception as e:
            state["errors"]. append(f"Entity extraction error: {str(e)}")
        return state
    
    def _extract_relations(self, state: GraphState) -> GraphState:
        """Step 3: 관계 추출"""
        triplets = []
        entities = state["entities"]
        
        for i, entity in enumerate(entities):
            try:
                # 이전 조항들을 컨텍스트로 제공
                context = entities[max(0, i-3):i]
                entity_triplets = self.relation_chain.extract(entity, context)
                
                if isinstance(entity_triplets, list):
                    triplets.extend(entity_triplets)
                else:
                    triplets.append(entity_triplets)
            except Exception as e:
                state["errors"].append(f"Relation extraction error for {entity.article_number}: {str(e)}")
        
        state["triplets"] = triplets
        state["document"].triplets = triplets
        return state
    
    def _validate_graph(self, state: GraphState) -> GraphState:
        """Step 4: 그래프 검증"""
        # 중복 제거 및 신뢰도 낮은 관계 필터링
        unique_triplets = {}
        for triplet in state["triplets"]:
            key = (triplet. subject, triplet.relation, triplet.object)
            if key not in unique_triplets or triplet.confidence > unique_triplets[key]. confidence:
                unique_triplets[key] = triplet
        
        state["triplets"] = list(unique_triplets.values())
        state["document"].triplets = state["triplets"]
        return state
    
    def process(self, document: LegalDocument) -> LegalDocument:
        """문서 처리 실행"""
        initial_state:  GraphState = {
            "document": document,
            "articles":  [],
            "entities": [],
            "triplets": [],
            "current_index": 0,
            "errors": []
        }
        
        final_state = self.workflow.invoke(initial_state)
        
        if final_state["errors"]:
            print(f"⚠️  Warning: {len(final_state['errors'])} errors occurred")
            for error in final_state["errors"]:
                print(f"  - {error}")
        
        return final_state["document"]

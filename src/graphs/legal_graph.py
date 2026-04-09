from typing import List, TypedDict
from langgraph.graph import StateGraph, END
from models.schemas import LegalEntity, GraphTriplet, LegalDocument
from chains.entity_extraction_chain import EntityExtractionChain
from chains.relation_extraction_chain import RelationExtractionChain
from utils.text_processor import split_and_categorize_articles
# from utils.text_processor import split_articles

# class GraphState(TypedDict):
#     """그래프 상태"""
#     document: LegalDocument
#     articles: List[str]
#     entities: List[LegalEntity]
#     triplets: List[GraphTriplet]
#     current_index: int
#     errors: List[str]

class GraphState(TypedDict):
    raw_text: str
    categorized_text: dict          # 파싱된 텍스트 딕셔너리
    entities: List[LegalEntity]   # 추출된 전체 노드
    global_entities: List[LegalEntity] # 총칙, 정의 등 글로벌 노드
    triplets: List[GraphTriplet]  # 추출된 전체 엣지
    document: LegalDocument       # 최종 문서 객체
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
        # articles = split_articles(state["document"].content)
        categorized_articles = split_and_categorize_articles(state["raw_text"])
        
        # state["articles"] = articles
        state["categorized_text"] = categorized_articles

        state["current_index"] = 0
        return state
    
    # def _extract_entities(self, state: GraphState) -> GraphState:
    #     """Step 2: 개체 추출"""
    #     try:
    #         entities = self.entity_chain.batch_extract(state["categorized_text"])
    #         state["entities"] = entities
    #         state["document"].entities = entities
    #     except Exception as e:
    #         state["errors"]. append(f"Entity extraction error: {str(e)}")
    #     return state
    def _extract_entities(self, state: GraphState) -> GraphState:
        """Step 2: 개체 추출 (부칙을 제외한 메인 조항 대상)"""
        try:
            # 메인 조항 텍스트 전체를 엔터티로 변환
            main_raw = state["categorized_text"]["main_raw"]
            entities = self.entity_chain.batch_extract(main_raw)
            
            # 파싱 단계에서 잡아둔 앞부분(Front) 조항과 매칭되는 엔터티들을 글로벌로 분리
            front_raw_texts = state["categorized_text"]["front_raw"]
            global_entities = [
                e for e in entities 
                if any(e.full_text in front_text for front_text in front_raw_texts)
            ]
            
            # 만약 위 매칭이 불안정하다면, 조항 번호로 하드코딩 필터링도 가능:
            # global_entities = [e for e in entities if e.article_number in ["제1조", "제2조", "제3조"]]
            
            state["entities"] = entities
            state["global_entities"] = global_entities
            state["document"].entities = entities
            
            # (선택) 부칙(Back)에서 시행일 파싱 로직 추가 가능
            # if state["categorized_text"]["back_raw"]:
            #     enforcement_date = extract_date_from_addenda(state["categorized_text"]["back_raw"][0])
            #     state["document"].enforcement_date = enforcement_date
                
        except Exception as e:
            state["errors"].append(f"Entity extraction error: {str(e)}")
        return state
    
    # def _extract_relations(self, state: GraphState) -> GraphState:
    #     """Step 3: 관계 추출"""
    #     triplets = []
    #     entities = state["entities"]
        
    #     for i, entity in enumerate(entities):
    #         try:
    #             # 이전 조항들을 컨텍스트로 제공
    #             context = entities[max(0, i-3):i]
    #             entity_triplets = self.relation_chain.extract(entity, context)
                
    #             if isinstance(entity_triplets, list):
    #                 triplets.extend(entity_triplets)
    #             else:
    #                 triplets.append(entity_triplets)
    #         except Exception as e:
    #             state["errors"].append(f"Relation extraction error for {entity.article_number}: {str(e)}")
        
    #     state["triplets"] = triplets
    #     state["document"].triplets = triplets
    #     return state
    
    def _extract_relations(self, state: GraphState) -> GraphState:
        """Step 3: 관계 추출 (Local + Global Context 주입)"""
        triplets = []
        entities = state["entities"]
        global_entities = state.get("global_entities", [])
        
        for i, entity in enumerate(entities):
            try:
                # Local Context: 슬라이딩 윈도우 (직전 3개 조항)
                local_context = entities[max(0, i-3):i]
                
                # 💡 핵심: Global Context와 Local Context를 분리하여 전달
                entity_triplets = self.relation_chain.extract(
                    entity=entity, 
                    local_context=local_context,
                    global_context=global_entities # 맨 앞에서 추출해둔 총칙/정의
                )
                
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
        "raw_text": document.content,   # A안: document.content 사용
        "categorized_text": {},          # ← 추가
        "document": document,
        "global_entities": [],           # ← 추가
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

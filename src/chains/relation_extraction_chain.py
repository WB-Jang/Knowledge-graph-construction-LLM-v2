from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from typing import List
from models.schemas import GraphTriplet, LegalEntity
from llm.llm_client import get_llm as llm
# from llm.llama_client import get_llm as opensource_llm


class RelationExtractionChain:
    """법률 관계 추출 체인"""
    
    def __init__(self, temperature: float = 0.0):
        self.llm = llm('openrouter')
        # self.llm = opensource_llm() # 추후에 변경해서도 테스트 가능
        self.temperature = temperature
        # JSON 리스트를 파싱하도록 변경
        self.parser = JsonOutputParser()
        
#         self.prompt = ChatPromptTemplate.from_messages([
#             ("system", """당신은 한국 법률 지식 그래프 전문가입니다.  
# 추출된 법률 개체 정보를 바탕으로 [주체 - 관계 - 대상] 트리플을 생성합니다.  

# 관계 유형:  
# - 상위조항: 다른 조항의 상위 개념
# - 참조함: 다른 조항을 참조
# - 준용함: 특정 조항의 규정을 유사한 다른 성격의 사항에 맞게 적용함.
# - 위임함: 조항의 세부 실행 사항을 하위 법령(시행령, 시행규칙)이나 고시로 정하도록 넘김.
# - 근거함: 특정 행정 처분이나 하위 조항이 상위의 어떤 조항으로부터 법적 효력을 얻는지 나타냄.

# 법적 논리 및 해석 관계 (Logical):
# - 정의함: 법령에서 사용되는 특정 용어나 개념의 법적 의미를 확정함.
# - 예외로함: 일반적인 원칙을 규정한 조항에 대해 특정한 경우 적용을 제외하거나 달리 정함.
# - 간주함: 본래 성질이 다르더라도 법적 목적을 위해 동일한 것으로 확정함 (문언: "~로 본다").
# - 추정함: 반대 증거가 제시되기 전까지 사실로 인정함 (문언: "~로 추정한다").
# - 우선함: 동일한 사안에 대해 여러 조항이 충돌할 때 먼저 적용되는 우선순위를 나타냄 (예: 특별법 우선).

# 행위 및 권무 관계 (Action & Obligation):
# - 요구함: 특정 주체가 반드시 이행해야 하는 작위 의무나 조건을 설정함 (문언: "~해야 한다").
# - 금지함: 해서는 안 되는 특정 행위나 부작위 의무를 설정함 (문언: "~해서는 아니 된다").
# - 허용함: 일정한 요건 하에 특정 행위를 할 수 있는 권리나 가능성을 부여함 (문언: "~할 수 있다").
# - 권한을가짐: 특정 행정 주체나 직위자가 법적 행위를 할 수 있는 자격과 범위를 명시함.
# - 승인을요구함: 특정 행위를 하기 위해 사전에 행정기관의 허가, 승인, 신고가 필요함을 나타냄.

# 제재 및 결과 관계 (Sanction):
# - 처벌대상임: 조항 위반 시 형벌(징역, 벌금 등)이 부과되는 직접적인 인과 관계를 나타냄.
# - 과태료대상임: 조항 위반 시 형벌이 아닌 행정질서벌로서 과태료가 부과됨을 나타냄.
# - 면제함: 특정 요건을 충족할 경우 부여된 의무나 처벌을 면제해 줌을 나타냄.
# - 가중함: 위반 행위의 횟수나 심각성에 따라 처벌 수위를 높여 적용하는 관계를 나타냄.

# **중요: 하나의 조항에서 여러 관계가 발견될 수 있습니다. JSON 배열로 반환하세요.**

# 출력 형식:
# [
#   {{
#     "subject": "관계의 주체",
#     "relation": "관계 유형 (위 목록 중 하나)",
#     "object": "관계의 대상",
#     "article_number": "조항 번호",
#     "confidence": 0.0~1.0 사이의 신뢰도
#   }}
# ]

# 빈 배열 []을 반환하지 마세요. 최소 1개 이상의 관계를 추출하세요."""),
#             ("user", """다음 법률 개체 정보에서 관계를 추출하세요: 

# 조항 번호: {article_number}
# 핵심 개념: {concept}
# 의무 주체: {subject}
# 행위: {action}
# 대상: {object}
# 원문: {full_text}

# 이전 조항들: {context}

# JSON 배열 형식으로만 응답하세요. 설명은 필요 없습니다.""")
#         ])
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 한국 법률 지식 그래프 전문가입니다.  
주어진 조항의 속성(Entity Type, Legal Force)과 원문을 분석하여 논리적으로 무결한 [주체 - 관계 - 대상] 트리플을 JSON 배열로 추출하세요.

[핵심 추출 가이드라인]
1. 주체(Subject) 결측치 처리: 의무 주체가 명시되지 않은 상태/정의 규정인 경우, 무리하게 주체를 생성하지 마세요. 대신 해당 조항의 '핵심 개념(Concept)'을 출발 노드(Subject)로 사용하여 <정의함>, <참조함>, <예외로함> 등의 관계를 만드세요.
2. 개체 타입(Entity Type) 활용: ACTOR(주체)는 주로 행위 관계(요구함/허용함)를, CONCEPT(개념)는 논리 관계(정의함/준용함)를 가집니다.
3. 전역 참조(Global Reference): '제2조의 규정에 따라'와 같은 문구가 있다면, 제공된 [핵심 앵커 조항]을 확인하여 반드시 해당 조항과 연결하세요.

[관계 유형 및 대분류(relation_category)]
- STRUCTURE (구조): 상위조항, 참조함, 준용함, 위임함, 근거함
- LOGICAL (논리): 정의함, 예외로함, 간주함, 추정함, 우선함
- ACTION (행위): 요구함, 금지함, 허용함, 권한을가짐, 승인을요구함
- SANCTION (제재): 처벌대상임, 과태료대상임, 면제함, 가중함

출력 형식 (JSON Array):
[
{{
    "subject": "행위의 주체 또는 출발 개념",
    "relation": "관계 유형",
    "relation_category": "대분류",
    "object": "행위의 대상 또는 도착 개념",
    "article_number": "조항 번호",
    "confidence": 0.0~1.0 사이의 확신도,
    "concepts": ["해당 관계를 설명하는 핵심 개념1", "개념2"]
  }}
]
빈 배열 []을 반환하지 마세요. 최소 1개 이상의 관계를 추출하세요."""),
            ("user", """[핵심 앵커 조항 (Global Context)]
{global_context}

[이전 조항 (Local Context)]
{local_context}

[현재 분석할 조항 정보]
- 조항 번호: {article_number}
- 노드 타입: {entity_type}
- 법적 강제성: {legal_force}
- 핵심 개념: {concept}
- 의무 주체: {subject}
- 행위: {action}
- 대상: {object}
- 원문: {full_text}

위 정보를 바탕으로 관계 트리플을 추출하세요. 설명 없이 JSON 배열만 반환하세요.""")
        ])
        self.chain = self.prompt | self.llm | self.parser
    
    # def extract(self, entity: LegalEntity, context: List[LegalEntity] = None) -> List[GraphTriplet]:
    #     """관계 추출 실행"""
    #     context_str = "\n".join([
    #         f"- {e.article_number}: {e.concept}"
    #         for e in (context or [])
    #     ])
        
    #     try:
    #         result = self.chain.invoke({
    #             "article_number": entity.article_number,
    #             "concept": entity.concept,
    #             "subject": entity.subject or "N/A",
    #             "action": entity.action or "N/A",
    #             "object": entity.object or "N/A",
    #             "full_text": entity.full_text,
    #             "context": context_str or "없음"
    #         })
            
    #         # JSON 리스트를 GraphTriplet 객체 리스트로 변환
    #         triplets = []
            
    #         # result가 리스트인 경우
    #         if isinstance(result, list):
    #             for item in result:
    #                 try:
    #                     triplet = GraphTriplet(**item)
    #                     triplets.append(triplet)
    #                 except Exception as e:
    #                     print(f"  ⚠️ 트리플 변환 실패: {e}")
    #                     continue
    #         # result가 딕셔너리인 경우 (단일 객체)
    #         elif isinstance(result, dict):
    #             try:
    #                 triplet = GraphTriplet(**result)
    #                 triplets.append(triplet)
    #             except Exception as e:
    #                 print(f"  ⚠️ 트리플 변환 실패: {e}")
            
    #         return triplets
            
    #     except Exception as e:
    #         print(f"⚠️ 관계 추출 중 오류: {e}")
    #         return []

    def extract(self, 
                entity: LegalEntity, 
                local_context: List[LegalEntity] = None,
                global_context: List[LegalEntity] = None) -> List[GraphTriplet]:
        """
        관계 추출 실행
        :param entity: 현재 타겟이 되는 조항 엔터티
        :param local_context: 슬라이딩 윈도우로 들어오는 직전 조항들 (보통 3~5개)
        :param global_context: 총칙, 정의 등 문서 전체에서 자주 참조되는 핵심 조항들
        """
        
        # 컨텍스트 문자열 포매팅 (엔터티의 타입과 개념을 함께 전달하여 그래프 연결점 제공)
        local_context_str = "\n".join([
            f"- [{e.article_number}] ({e.entity_type}): {e.concept} / 주체: {e.subject or '없음'}"
            for e in (local_context or [])
        ])
        
        global_context_str = "\n".join([
            f"- [{e.article_number}] ({e.entity_type}): {e.concept}"
            for e in (global_context or [])
        ])
        
        try:
            result = self.chain.invoke({
                "global_context": global_context_str or "제공되지 않음",
                "local_context": local_context_str or "제공되지 않음",
                "article_number": entity.article_number,
                "entity_type": getattr(entity, 'entity_type', "N/A"),
                "legal_force": getattr(entity, 'legal_force', "N/A"),
                "concept": entity.concept,
                "subject": entity.subject or "null",
                "action": entity.action or "null",
                "object": entity.object or "null",
                "full_text": entity.full_text
            })
            
            triplets = []
            
            if isinstance(result, list):
                for item in result:
                    try:
                        triplet = GraphTriplet(**item)
                        triplets.append(triplet)
                    except Exception as e:
                        print(f"  ⚠️ 트리플 변환 실패: {e} / 원본 데이터: {item}")
                        continue
            elif isinstance(result, dict):
                try:
                    triplet = GraphTriplet(**result)
                    triplets.append(triplet)
                except Exception as e:
                    print(f"  ⚠️ 트리플 변환 실패: {e}")
            
            return triplets
            
        except Exception as e:
            print(f"⚠️ {entity.article_number} 관계 추출 중 오류: {e}")
            return []
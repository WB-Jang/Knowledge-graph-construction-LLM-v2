from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from typing import List
from models.schemas import GraphTriplet, LegalEntity
from llm.gemini_client import get_llm as gemini_llm
# from llm.llama_client import get_llm as opensource_llm


class RelationExtractionChain:
    """법률 관계 추출 체인"""
    
    def __init__(self, temperature: float = 0.0):
        self.llm = gemini_llm()
        # self.llm = opensource_llm() # 추후에 변경해서도 테스트 가능
        self.temperature = temperature
        # JSON 리스트를 파싱하도록 변경
        self.parser = JsonOutputParser()
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 한국 법률 지식 그래프 전문가입니다.  
추출된 법률 개체 정보를 바탕으로 [주체 - 관계 - 대상] 트리플을 생성합니다.  

관계 유형:  
- 상위조항: 다른 조항의 상위 개념
- 참조함: 다른 조항을 참조
- 준용함: 특정 조항의 규정을 유사한 다른 성격의 사항에 맞게 적용함.
- 위임함: 조항의 세부 실행 사항을 하위 법령(시행령, 시행규칙)이나 고시로 정하도록 넘김.
- 근거함: 특정 행정 처분이나 하위 조항이 상위의 어떤 조항으로부터 법적 효력을 얻는지 나타냄.

법적 논리 및 해석 관계 (Logical):
- 정의함: 법령에서 사용되는 특정 용어나 개념의 법적 의미를 확정함.
- 예외로함: 일반적인 원칙을 규정한 조항에 대해 특정한 경우 적용을 제외하거나 달리 정함.
- 간주함: 본래 성질이 다르더라도 법적 목적을 위해 동일한 것으로 확정함 (문언: "~로 본다").
- 추정함: 반대 증거가 제시되기 전까지 사실로 인정함 (문언: "~로 추정한다").
- 우선함: 동일한 사안에 대해 여러 조항이 충돌할 때 먼저 적용되는 우선순위를 나타냄 (예: 특별법 우선).

행위 및 권무 관계 (Action & Obligation):
- 요구함: 특정 주체가 반드시 이행해야 하는 작위 의무나 조건을 설정함 (문언: "~해야 한다").
- 금지함: 해서는 안 되는 특정 행위나 부작위 의무를 설정함 (문언: "~해서는 아니 된다").
- 허용함: 일정한 요건 하에 특정 행위를 할 수 있는 권리나 가능성을 부여함 (문언: "~할 수 있다").
- 권한을가짐: 특정 행정 주체나 직위자가 법적 행위를 할 수 있는 자격과 범위를 명시함.
- 승인을요구함: 특정 행위를 하기 위해 사전에 행정기관의 허가, 승인, 신고가 필요함을 나타냄.

제재 및 결과 관계 (Sanction):
- 처벌대상임: 조항 위반 시 형벌(징역, 벌금 등)이 부과되는 직접적인 인과 관계를 나타냄.
- 과태료대상임: 조항 위반 시 형벌이 아닌 행정질서벌로서 과태료가 부과됨을 나타냄.
- 면제함: 특정 요건을 충족할 경우 부여된 의무나 처벌을 면제해 줌을 나타냄.
- 가중함: 위반 행위의 횟수나 심각성에 따라 처벌 수위를 높여 적용하는 관계를 나타냄.

**중요: 하나의 조항에서 여러 관계가 발견될 수 있습니다. JSON 배열로 반환하세요.**

출력 형식:
[
  {{
    "subject": "관계의 주체",
    "relation": "관계 유형 (위 목록 중 하나)",
    "object": "관계의 대상",
    "article_number": "조항 번호",
    "confidence": 0.0~1.0 사이의 신뢰도
  }}
]

빈 배열 []을 반환하지 마세요. 최소 1개 이상의 관계를 추출하세요."""),
            ("user", """다음 법률 개체 정보에서 관계를 추출하세요: 

조항 번호: {article_number}
핵심 개념: {concept}
의무 주체: {subject}
행위: {action}
대상: {object}
원문: {full_text}

이전 조항들: {context}

JSON 배열 형식으로만 응답하세요. 설명은 필요 없습니다.""")
        ])
        
        self.chain = self.prompt | self.llm | self.parser
    
    def extract(self, entity: LegalEntity, context: List[LegalEntity] = None) -> List[GraphTriplet]:
        """관계 추출 실행"""
        context_str = "\n".join([
            f"- {e.article_number}: {e.concept}"
            for e in (context or [])
        ])
        
        try:
            result = self.chain.invoke({
                "article_number": entity.article_number,
                "concept": entity.concept,
                "subject": entity.subject or "N/A",
                "action": entity.action or "N/A",
                "object": entity.object or "N/A",
                "full_text": entity.full_text,
                "context": context_str or "없음"
            })
            
            # JSON 리스트를 GraphTriplet 객체 리스트로 변환
            triplets = []
            
            # result가 리스트인 경우
            if isinstance(result, list):
                for item in result:
                    try:
                        triplet = GraphTriplet(**item)
                        triplets.append(triplet)
                    except Exception as e:
                        print(f"  ⚠️ 트리플 변환 실패: {e}")
                        continue
            # result가 딕셔너리인 경우 (단일 객체)
            elif isinstance(result, dict):
                try:
                    triplet = GraphTriplet(**result)
                    triplets.append(triplet)
                except Exception as e:
                    print(f"  ⚠️ 트리플 변환 실패: {e}")
            
            return triplets
            
        except Exception as e:
            print(f"⚠️ 관계 추출 중 오류: {e}")
            return []

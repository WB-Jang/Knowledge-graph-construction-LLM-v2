from langchain.prompts import ChatPromptTemplate
from langchain. output_parsers import PydanticOutputParser
from typing import List
from ..models.schemas import GraphTriplet, LegalEntity
from ..llm.gemini_client import get_llm as gemini_llm
from ..llm.llama_client import get_llm as opensource_llm


class RelationExtractionChain:
    """법률 관계 추출 체인"""
    
    def __init__(self, temperature: float = 0.0):
        self.llm = opensource_llm()
        self.temperature = temperature
        self. parser = PydanticOutputParser(pydantic_object=GraphTriplet)
        
        self.prompt = ChatPromptTemplate. from_messages([
            ("system", """당신은 한국 법률 지식 그래프 전문가입니다.  
추출된 법률 개체 정보를 바탕으로 [주체 - 관계 - 대상] 트리플을 생성합니다.  

관계 유형:  
- 상위조항:  다른 조항의 상위 개념
- 참조함:  다른 조항을 참조
- 예외로함: 다른 조항의 예외 사항
- 처벌대상임: 위반 시 처벌 관계
- 정의함: 용어나 개념을 정의
- 요구함: 특정 행위나 조건을 요구
- 금지함: 특정 행위를 금지

출력은 반드시 JSON 형식으로 작성하세요.
{format_instructions}"""),
            ("user", """다음 법률 개체 정보에서 관계를 추출하세요: 

조항 번호: {article_number}
핵심 개념: {concept}
의무 주체: {subject}
행위:  {action}
대상: {object}
원문: {full_text}

이전 조항들:  {context}""")
        ])
        
        self.chain = self.prompt | self.llm | self.parser
    
    def extract(self, entity: LegalEntity, context: List[LegalEntity] = None) -> List[GraphTriplet]:
        """관계 추출 실행"""
        context_str = "\n".join([
            f"- {e.article_number}: {e. concept}"
            for e in (context or [])
        ])
        
        try:
            result = self.chain.invoke({
                "article_number": entity. article_number,
                "concept": entity.concept,
                "subject": entity.subject or "N/A",
                "action":  entity.action or "N/A",
                "object": entity. object or "N/A",
                "full_text": entity. full_text,
                "context": context_str or "없음",
                "format_instructions": self.parser.get_format_instructions()
            })
            
            # 단일 결과를 리스트로 변환
            if isinstance(result, GraphTriplet):
                return [result]
            return result if isinstance(result, list) else [result]
            
        except Exception as e:
            print(f"⚠️ 관계 추출 중 오류: {e}")
            return []

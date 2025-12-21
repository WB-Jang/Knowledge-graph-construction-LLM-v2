from langchain. prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from typing import List
from .. models.schemas import LegalEntity
from ..llm.gemini_client import get_llm


class EntityExtractionChain:  
    """법률 개체 추출 체인"""
    
    def __init__(self, temperature: float = 0.0):
        self.llm = get_llm()
        # Gemini는 temperature를 생성 시 지정
        self.temperature = temperature
        self.parser = PydanticOutputParser(pydantic_object=LegalEntity)
        
        # Chat 형식 프롬프트
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 한국 법률 전문 데이터 엔지니어입니다.   
법령 텍스트를 분석하여 구조화된 정보를 추출하는 전문가입니다.  

다음 정보를 정확하게 추출하세요:
1. 조항 번호 (예: 제1조, 제2조의2, 제3조제1항)
2. 핵심 개념 (해당 조항의 주제)
3. 의무 주체 (누가)
4. 행위 (무엇을 하는지)
5. 대상 (무엇에 대해)

출력은 반드시 JSON 형식으로 작성하세요.
{format_instructions}"""),
            ("user", "다음 법령 조항을 분석하세요:\n\n{text}")
        ])
        
        self.chain = self.prompt | self.llm | self.parser
    
    def extract(self, text: str) -> LegalEntity:
        """개체 추출 실행"""
        try:
            result = self.chain.invoke({
                "text": text,
                "format_instructions": self. parser.get_format_instructions()
            })
            return result
        except Exception as e:  
            print(f"⚠️ 개체 추출 중 오류:  {e}")
            # 기본값 반환
            return LegalEntity(
                article_number="Unknown",
                concept="Unknown",
                subject=None,
                action=None,
                object=None,
                full_text=text
            )
    
    def batch_extract(self, texts: List[str]) -> List[LegalEntity]:
        """여러 조항 일괄 추출"""
        results = []
        for text in texts:
            results.append(self.extract(text))
        return results

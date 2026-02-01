from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException
from typing import List
from models.schemas import LegalEntity
from llm.gemini_client import get_llm as gemini_llm
import json
# from llm.llama_client import get_llm as opensource_llm

class EntityExtractionChain:  
    """법률 개체 추출 체인"""
    
    def __init__(self, temperature: float = 0.0):
        self.llm = gemini_llm()
        # self.llm = opensource_llm() # 추후에 변경해서도 테스트 가능
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

⚠️ 중요: 
- 하나의 조항에 여러 항이 있더라도, 전체를 통합하여 **단일 JSON 객체**만 반환하세요.
- 배열이나 리스트를 반환하지 마세요.
- article_number는 전체 조항을 대표하는 하나의 번호만 사용하세요.

출력은 반드시 다음 JSON 형식으로 작성하세요:
{format_instructions}"""),
            ("user", "다음 법령 조항을 분석하세요:\n\n{text}")
        ])
        
        self.chain = self.prompt | self.llm | self.parser
    
    def extract(self, text: str) -> LegalEntity:
        """개체 추출 실행"""
        try:
            result = self.chain.invoke({
                "text": text,
                "format_instructions": self.parser.get_format_instructions()
            })
            return result
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ 개체 추출 중 오류: {e}")
            
            # LLM이 리스트를 반환한 경우 처리
            if "Input should be a valid dictionary" in error_msg and "input_type=list" in error_msg:
                try:
                    # 에러 메시지에서 JSON 추출 시도
                    import json
                    import re
                    
                    # completion 부분에서 JSON 추출
                    match = re.search(r'completion \[(.*?)\]\.', error_msg, re.DOTALL)
                    if match:
                        json_str = '[' + match.group(1) + ']'
                        entities_list = json.loads(json_str)
                        
                        if entities_list and len(entities_list) > 0:
                            # 첫 번째 항목 사용
                            first_entity = entities_list[0]
                            print(f"   ℹ️ 리스트에서 첫 번째 항목 사용: {first_entity.get('article_number', 'Unknown')}")
                            return LegalEntity(**first_entity)
                except Exception as parse_error:
                    print(f"   ⚠️ 리스트 파싱 실패: {parse_error}")
            
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

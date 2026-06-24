from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
# from langchain_core.exceptions import OutputParserException
from typing import List
from models.schemas import LegalEntity
from llm.llm_client import get_llm as llm
# import json
# from llm.llama_client import get_llm as opensource_llm

class EntityExtractionChain:  
    """법률 개체 추출 체인"""
    
    def __init__(self, temperature: float = 0.0):
        self.llm = llm('openrouter')
        # Args:
        # provider: "gemini" | "groq" | "openrouter" | "local"
        #           None이면 환경변수 LLM_PROVIDER 확인 (기본값: "groq")
        # # self.llm = opensource_llm() # 추후에 변경해서도 테스트 가능
        # Gemini는 temperature를 생성 시 지정
        self.temperature = temperature
        self.parser = PydanticOutputParser(pydantic_object=LegalEntity)
        
        # Chat 형식 프롬프트
#         self.prompt = ChatPromptTemplate.from_messages([
#             ("system", """당신은 한국 법률 전문 데이터 엔지니어입니다.   
# 법령 텍스트를 분석하여 구조화된 정보를 추출하는 전문가입니다.  

# 다음 정보를 정확하게 추출하세요:
# 1. 조항 번호 (예: 제1조, 제2조의2, 제3조제1항)
# 2. 핵심 개념 (해당 조항의 주제)
# 3. 의무 주체 (누가)
# 4. 행위 (무엇을 하는지)
# 5. 대상 (무엇에 대해)

# ⚠️ 중요: 
# - 하나의 조항에 여러 항이 있더라도, 전체를 통합하여 **단일 JSON 객체**만 반환하세요.
# - 배열이나 리스트를 반환하지 마세요.
# - article_number는 전체 조항을 대표하는 하나의 번호만 사용하세요.

# 출력은 반드시 다음 JSON 형식으로 작성하세요:
# {format_instructions}"""),
#             ("user", "다음 법령 조항을 분석하세요:\n\n{text}")
#         ])
        # Chat 형식 프롬프트 개선
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 한국 법률 및 금융 규제 전문 데이터 엔지니어입니다.   
법령 텍스트를 분석하여 지식 그래프 구축을 위한 구조화된 노드(Node) 정보를 추출하세요.  

다음 정보를 정확하게 추출하세요:
1. 조항 번호 article_number (예: 제1조, 제2조의2, 제3조제1항)
2. 계층 인덱스 structural_index: [장번호, 절번호, 조번호, 항번호] 형태의 정수 배열. 파악 불가 시 []
3. 노드 타입 entity_type: 조항의 성격에 따라 다음 중 하나 선택
   - ACTOR: 특정 주체(기관, 사람)의 권한/의무를 규정
   - CONCEPT: 용어 정의, 개념 설명
   - REGULATION: 일반적인 규제/제한 사항
   - PENALTY: 처벌, 과태료, 제재 관련
   - PROCEDURE: 신고, 인가, 절차 관련
   - DEFINITION: 법에서 사용하는 용어를 정의
4. 핵심 개념 concept (해당 조항의 핵심 키워드)
5. 의무 주체 subject (주어가 되는 고유명사 또는 일반명사)
6. 행위 action (서술어 중심의 핵심 행위)
7. 대상 object (목적어가 되는 고유명사 또는 일반명사)
8. 법적 강제성 legal_force: 다음 중 하나
   - MANDATORY: "~하여야 한다", "~해야 한다" 등 의무 규정
   - PROHIBITIVE: "~해서는 아니 된다", "~금지" 등 금지 규정
   - PERMISSIVE: "~할 수 있다" 등 허용 규정
   - DEFINITIONAL: 용어/개념을 정의하는 규정
   - 파악 불가 시 null
9. 원문 full_text

⚠️ 중요: 주체(subject)와 대상(object) 추출 규칙
- 반드시 군더더기 없는 **단일 명사 또는 짧은 명사구** 형태로만 추출하세요. 수식어나 서술어는 철저히 배제하세요.
- 복잡한 수식어구는 모두 '행위(action)'나 '원문(full_text)'에 남겨두어야 합니다.
  * ❌ 나쁜 예 (서술형): "인가를 받지 않고 영업을 영위하는 금융기관"
  * ⭕ 좋은 예 (명사형): "금융기관"
  * ❌ 나쁜 예 (서술형): "대통령령으로 정하는 바에 따른 과징금 및 과태료"
  * ⭕ 좋은 예 (명사형): "과징금", "과태료"
  * ❌ 나쁜 예 (서술형): "위험가중자산에 대한 자기자본비율"
  * ⭕ 좋은 예 (명사형): "자기자본비율"

⚠️ 구조화 규칙: 
- 하나의 조항에 여러 항이 있더라도, 전체를 통합하여 **단일 JSON 객체**만 반환하세요.
- 배열이나 리스트를 반환하지 마세요.
- article_number는 전체 조항을 대표하는 하나의 번호만 사용하세요.
- 해당 항목이 텍스트에 명시되어 있지 않다면 null을 반환하세요. 억지로 만들어내지 마세요.

출력은 반드시 다음 JSON 형식으로 작성하세요:
{format_instructions}"""),
            ("user", "다음 법령 조항을 분석하여 명사 중심의 개체를 추출하세요:\n\n{text}")
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
                entity_type="REGULATION",
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

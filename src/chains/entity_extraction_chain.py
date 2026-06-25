from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from typing import List, Optional
from pydantic import BaseModel, Field
from models.schemas import LegalEntity
from llm.llm_client import get_generator_llm


class _EntitySemanticFields(BaseModel):
    """LLM이 추출할 '의미' 필드만 담는 최소 스키마.

    article_number/hang_number/structural_index/cross_law_refs 등 결정론적 필드와
    full_text·파이프라인 메타데이터는 LLM이 만들지 않고 코드(파서)가 채운다.
    이렇게 출력 스키마를 좁히면 JSON 파싱 실패와 환각이 크게 줄어든다.
    """
    entity_type: Optional[str] = Field(default=None, description="ACTOR/CONCEPT/REGULATION/PENALTY/PROCEDURE/DEFINITION")
    concept: Optional[str] = Field(default=None, description="이 항의 핵심 개념(짧은 명사구)")
    subject: Optional[str] = Field(default=None, description="의무·권한의 주체(단일 명사구), 없으면 null")
    action: Optional[str] = Field(default=None, description="핵심 행위")
    object: Optional[str] = Field(default=None, description="행위 대상(단일 명사구), 없으면 null")
    legal_force: Optional[str] = Field(default=None, description="MANDATORY/PROHIBITIVE/PERMISSIVE/DEFINITIONAL/null")


class EntityExtractionChain:
    """법률 개체 추출 체인"""

    def __init__(self, temperature: float = 0.0):
        self.llm = get_generator_llm()
        self.temperature = temperature
        self.parser = PydanticOutputParser(pydantic_object=_EntitySemanticFields)
        
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
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 한국 법률 및 금융 규제 전문 데이터 엔지니어입니다.
법령의 **단일 항(項) 단위** 텍스트를 분석하여 지식 그래프 구축을 위한 노드(Node) 정보를 추출하세요.
입력 텍스트는 조 전체가 아니라 하나의 항(①, ②, … 또는 항이 없는 단독 조문)입니다.

추출할 정보:
1. article_number: 조항 번호 (예: 제28조). 텍스트에 명시된 번호 사용.
2. entity_type: 이 항의 성격
   - ACTOR: 특정 주체(기관, 사람)의 권한·의무 규정
   - CONCEPT: 용어 정의·개념 설명
   - REGULATION: 일반 규제·제한
   - PENALTY: 처벌·과태료·제재
   - PROCEDURE: 신고·인가·절차
   - DEFINITION: 법령 용어 정의
3. concept: 이 항의 핵심 키워드 (짧은 명사구)
4. subject: 의무·권한의 주체 — **단일 명사 또는 짧은 명사구**. 없으면 null.
5. action: 핵심 행위 (서술어 중심)
6. object: 행위의 대상 — **단일 명사 또는 짧은 명사구**. 없으면 null.
7. legal_force: MANDATORY / PROHIBITIVE / PERMISSIVE / DEFINITIONAL / null
8. full_text: 입력된 원문 그대로

subject/object 추출 원칙:
- 명사형으로만. 수식어·서술어 금지.
  ❌ "인가를 받지 않고 영업을 영위하는 금융기관" → ⭕ "금융기관"
  ❌ "대통령령으로 정하는 바에 따른 과태료" → ⭕ "과태료"
- 명시되지 않으면 null. 억지로 생성하지 마세요.

출력은 단일 JSON 객체만 반환하세요 (배열 금지):
{format_instructions}"""),
            ("user", """다음 법령 항(項) 텍스트에서 개체를 추출하세요.

[법률 정보]
법률명: {law_title}

[타 법령 참조 목록 (이 항에서 인용하는 타 법령 조항 — 본 법령 조항이 아님)]
{cross_law_refs}

[분석할 항 텍스트]
{text}""")
        ])
        self.chain = self.prompt | self.llm | self.parser
    
    def extract(self, text: str, cross_law_refs: list = None,
                law_title: str = None) -> LegalEntity:
        """개체 추출 실행. LLM은 의미 필드만 추출하고, full_text는 코드가 주입한다.

        cross_law_refs: 이 항에서 인용하는 타 법령 조항 목록 (컨텍스트 주입용).
        law_title: 본 법률 이름 (대명사 해소용).
        결정론적 필드(article_number/hang_number/structural_index 등)는 호출측(legal_graph)에서
        파서 값으로 덮어쓴다.
        """
        refs_str = "\n".join(f"- {r}" for r in (cross_law_refs or [])) or "없음"

        def _build(sem: _EntitySemanticFields) -> LegalEntity:
            return LegalEntity(
                entity_type=sem.entity_type,
                concept=sem.concept or "Unknown",
                subject=sem.subject,
                action=sem.action,
                object=sem.object,
                legal_force=sem.legal_force,
                full_text=text,
                cross_law_refs=cross_law_refs or [],
            )

        try:
            sem = self.chain.invoke({
                "text": text,
                "law_title": law_title or "본 법률",
                "cross_law_refs": refs_str,
                "format_instructions": self.parser.get_format_instructions()
            })
            return _build(sem)
        except Exception as e:
            print(f"⚠️ 개체 추출 중 오류: {e}")

            # 복구: 에러 메시지의 completion JSON에서 의미 필드만 살려 재구성
            import json
            import re as _re
            for pattern in [r'completion (\{.*?\})', r'\{[^{}]*\}']:
                match = _re.search(pattern, str(e), _re.DOTALL)
                if not match:
                    continue
                try:
                    raw = match.group(1) if match.groups() else match.group(0)
                    data = json.loads(raw)
                    valid = set(_EntitySemanticFields.model_fields.keys())
                    data = {k: v for k, v in data.items() if k in valid}
                    salvaged = _build(_EntitySemanticFields(**data))
                    print(f"   ♻️ 부분 JSON 복구 성공: concept={salvaged.concept}")
                    return salvaged
                except Exception as salvage_err:
                    print(f"   ⚠️ 부분 JSON 복구 실패: {salvage_err}")
                    break

            # 최종 폴백: 기본값 엔티티 (파이프라인 중단 방지)
            return _build(_EntitySemanticFields(entity_type="REGULATION", concept="Unknown"))
    
    def batch_extract(self, texts: List[str]) -> List[LegalEntity]:
        """여러 조항 일괄 추출"""
        results = []
        for text in texts:
            results.append(self.extract(text))
        return results

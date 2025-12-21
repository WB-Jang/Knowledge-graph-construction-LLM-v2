from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class LegalEntity(BaseModel):
    """법률 개체"""
    article_number: str = Field(description="조항 번호")
    concept: str = Field(description="핵심 개념")
    subject: Optional[str] = Field(default=None, description="의무 주체")
    action: Optional[str] = Field(default=None, description="행위")
    object: Optional[str] = Field(default=None, description="대상")
    full_text: str = Field(description="원문")

class RelationType(str, Enum):
    # --- 구조 및 참조 관계 ---
    PARENT_ARTICLE = "상위조항"      # 장-절-조-항-호 간의 계층 구조
    REFERS_TO = "참조함"           # 단순 인용 및 참조
    APPLIES_MUTATIS_MUTANDIS = "준용함" # 다른 조항을 성질에 맞게 적용
    DELEGATES_TO = "위임함"        # 하위 법령(시행령/규칙)으로 세부사항 위임
    
    # --- 논리 및 효력 관계 ---
    EXCEPTION_TO = "예외로함"       # 일반 원칙에 대한 특례
    SUPERSEDES = "우선함"          # 특별법 우선의 원칙 등 상충 시 우선순위
    BASED_ON = "근거함"            # 행정 처분 등의 법적 근거
    
    # --- 행위 및 규제 관계 ---
    DEFINES = "정의함"             # 용어 또는 개념의 정의
    REQUIRES = "요구함"            # 작위 의무 (해야 한다)
    PROHIBITS = "금지함"           # 부작위 의무 (해서는 안 된다)
    ALLOWS = "허용함"              # 권리 부여 또는 허가 사항
    
    # --- 제재 및 책임 관계 ---
    PUNISHMENT_FOR = "처벌대상임"    # 형벌(징역, 벌금) 대상
    PENALTY_FOR = "과태료대상임"     # 행정질서벌(과태료) 대상
    RESPONSIBLE_FOR = "책임이있음"   # 손해배상 등 민사적 책임
    
    # --- 주체 및 절차 관계 ---
    HAS_AUTHORITY = "권한을가짐"    # 행정 주체의 직무 범위
    APPLIES_TO = "적용대상임"       # 법 적용을 받는 주체/대상 명시
    FOLLOWS_PROCEDURE = "절차를따름" # 신고, 승인, 협의 등 행정 절차 연결


class GraphTriplet(BaseModel):
    """지식 그래프 트리플"""
    subject: str = Field(description="주체")
    relation: str = Field(description="관계")
    object: str = Field(description="대상")
    article_number: str = Field(description="조항 번호")
    confidence: float = Field(default=1.0, description="신뢰도")


class LegalDocument(BaseModel):
    """법률 문서"""
    title: str = Field(description="법령명")
    law_number: str = Field(description="법령 번호")
    content: str = Field(description="법령 내용")
    entities: List[LegalEntity] = Field(default_factory=list)
    triplets: List[GraphTriplet] = Field(default_factory=list)

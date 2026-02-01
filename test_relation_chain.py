#!/usr/bin/env python3
"""관계 추출 체인 테스트"""
import sys
sys.path.insert(0, '/app/src')

from models.schemas import LegalEntity, GraphTriplet
from chains.relation_extraction_chain import RelationExtractionChain

print("=== 관계 추출 체인 테스트 ===\n")

# 테스트 데이터
entity = LegalEntity(
    article_number="제1조",
    concept="목적",
    subject="이 법",
    action="규율함",
    object="자본시장에서의 금융혁신과 공정한 경쟁 촉진",
    full_text="이 법은 자본시장에서의 금융혁신과 공정한 경쟁을 촉진하고 투자자를 보호하며 금융투자업을 건전하게 육성함으로써 자본시장의 공정성·신뢰성 및 효율성을 높여 국민경제의 발전에 이바지함을 목적으로 한다."
)

print(f"조항: {entity.article_number}")
print(f"개념: {entity.concept}")
print(f"원문: {entity.full_text[:50]}...\n")

# 체인 실행
print("관계 추출 중...")
chain = RelationExtractionChain()
result = chain.extract(entity)

print(f"\n✅ 추출된 관계: {len(result)}개\n")

for i, triplet in enumerate(result, 1):
    print(f"{i}. {triplet.subject} --[{triplet.relation}]--> {triplet.object}")
    print(f"   조항: {triplet.article_number}, 신뢰도: {triplet.confidence}")

print("\n테스트 완료!")

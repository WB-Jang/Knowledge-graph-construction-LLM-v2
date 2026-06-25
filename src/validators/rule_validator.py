"""Deterministic rule-based validator for LegalEntity and GraphTriplet objects.

Applied before the LLM evaluator to catch cheap/obvious errors without LLM cost.
All checks are O(1) per item and have zero API cost.

문제 5 대응: enum에 없는 relation 값을 런타임에 수집하여 세션이 끝날 때
data/output/unknown_relations.csv에 기록한다. 이를 검토해 주기적으로 enum을 확장한다.
"""
import csv
import os
import re
from collections import Counter
from typing import List, Tuple
from models.schemas import LegalEntity, GraphTriplet, RelationType

# Set of valid relation strings derived from the RelationType enum
VALID_RELATIONS = {r.value for r in RelationType}

# 런타임 unknown relation 집계 (세션 내 누적)
_UNKNOWN_RELATION_COUNTER: Counter = Counter()

_UNKNOWN_RELATIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "output", "unknown_relations.csv"
)


def flush_unknown_relations():
    """세션 종료 시 또는 수동 호출로 미등록 relation을 CSV에 기록한다."""
    if not _UNKNOWN_RELATION_COUNTER:
        return
    os.makedirs(os.path.dirname(_UNKNOWN_RELATIONS_PATH), exist_ok=True)
    with open(_UNKNOWN_RELATIONS_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["relation", "count"])
        for rel, cnt in _UNKNOWN_RELATION_COUNTER.most_common():
            w.writerow([rel, cnt])
    print(f"📋 미등록 relation {len(_UNKNOWN_RELATION_COUNTER)}종 → {_UNKNOWN_RELATIONS_PATH}")

# Article number format: 제N조, 제N조의N, 제N조의N제N항, etc.
ARTICLE_NUMBER_RE = re.compile(r'^제\d+조(?:의\d+)?(?:제\d+항(?:제\d+호)?)?$')

# Max word count for subject/object noun phrases (too long = a clause, not a noun)
MAX_NOUN_WORDS = 10


def _word_count(text: str) -> int:
    return len(text.split())


class RuleValidationResult:
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def __repr__(self) -> str:
        return f"RuleValidationResult(passed={self.passed}, errors={self.errors}, warnings={self.warnings})"


def validate_entity(entity: LegalEntity) -> RuleValidationResult:
    """Validate a single LegalEntity."""
    result = RuleValidationResult()

    # 1. article_number must match expected format
    if entity.article_number and entity.article_number not in ("Unknown", "N/A"):
        num = entity.article_number.replace(" ", "")
        if not ARTICLE_NUMBER_RE.match(num):
            result.errors.append(f"article_number format invalid: '{entity.article_number}'")

    # 2. concept must be present
    if not entity.concept or entity.concept == "Unknown":
        result.errors.append("concept is missing or Unknown")

    # 3. subject noun phrase length
    if entity.subject and _word_count(entity.subject) > MAX_NOUN_WORDS:
        result.warnings.append(f"subject may be a clause, not a noun ({_word_count(entity.subject)} words): '{entity.subject[:50]}'")

    # 4. object noun phrase length
    if entity.object and _word_count(entity.object) > MAX_NOUN_WORDS:
        result.warnings.append(f"object may be a clause, not a noun ({_word_count(entity.object)} words): '{entity.object[:50]}'")

    # 5. full_text must be non-empty
    if not entity.full_text or not entity.full_text.strip():
        result.errors.append("full_text is empty")

    return result


def validate_triplet(triplet: GraphTriplet) -> RuleValidationResult:
    """Validate a single GraphTriplet."""
    result = RuleValidationResult()

    # 1. Self-reference (subject == object) is invalid
    if triplet.subject.strip() == triplet.object.strip():
        result.errors.append(f"self-reference: subject == object == '{triplet.subject}'")

    # 2. Relation must be in the defined enum (문제 5: unknown 집계)
    if triplet.relation not in VALID_RELATIONS:
        result.errors.append(f"unknown relation type: '{triplet.relation}'")
        _UNKNOWN_RELATION_COUNTER[triplet.relation] += 1

    # 3. Subject and object must be non-empty
    if not triplet.subject.strip():
        result.errors.append("subject is empty")
    if not triplet.object.strip():
        result.errors.append("object is empty")

    # 4. Confidence must be 0–1
    if not (0.0 <= triplet.confidence <= 1.0):
        result.errors.append(f"confidence out of range: {triplet.confidence}")

    # 5. Subject/object noun phrase length
    if _word_count(triplet.subject) > MAX_NOUN_WORDS:
        result.warnings.append(f"subject may be a clause ({_word_count(triplet.subject)} words)")
    if _word_count(triplet.object) > MAX_NOUN_WORDS:
        result.warnings.append(f"object may be a clause ({_word_count(triplet.object)} words)")

    return result


def validate_article_triplets(
    entity: LegalEntity,
    triplets: List[GraphTriplet],
) -> Tuple[List[GraphTriplet], List[str]]:
    """Run rule validation on all triplets for one article.

    Returns (valid_triplets, error_messages).
    Invalid triplets are filtered out; warnings are printed but not filtered.
    """
    valid: List[GraphTriplet] = []
    errors: List[str] = []

    entity_result = validate_entity(entity)
    if not entity_result.passed:
        errors.extend([f"[entity:{entity.article_number}] {e}" for e in entity_result.errors])
    for w in entity_result.warnings:
        print(f"  ⚠️  [rule_warn entity:{entity.article_number}] {w}")

    for triplet in triplets:
        t_result = validate_triplet(triplet)
        if t_result.passed:
            valid.append(triplet)
        else:
            for e in t_result.errors:
                errors.append(f"[triplet:{entity.article_number}] {e}")
        for w in t_result.warnings:
            print(f"  ⚠️  [rule_warn triplet:{entity.article_number}] {w}")

    return valid, errors

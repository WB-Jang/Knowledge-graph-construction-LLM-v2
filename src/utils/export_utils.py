"""추출된 노드와 트리플을 파일로 내보내는 유틸리티"""
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from models.schemas import LegalDocument, LegalEntity, GraphTriplet
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "output")
def _make_output_dir(base_name: str) -> str:
    """타임스탬프 기반 출력 디렉토리 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(OUTPUT_DIR, f"{base_name}_{timestamp}")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir
def export_nodes_csv(entities: List[LegalEntity], filepath: str):
    """노드를 CSV로 저장"""
    fieldnames = [
        "article_number", "structural_index", "entity_type",
        "concept", "subject", "action", "object",
        "legal_force", "full_text"
    ]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for e in entities:
            writer.writerow({
                "article_number": e.article_number,
                "structural_index": str(e.structural_index),
                "entity_type": e.entity_type,
                "concept": e.concept,
                "subject": e.subject or "",
                "action": e.action or "",
                "object": e.object or "",
                "legal_force": e.legal_force or "",
                "full_text": e.full_text.replace("\n", " "),
            })
def export_triplets_csv(triplets: List[GraphTriplet], filepath: str):
    """트리플을 CSV로 저장"""
    fieldnames = [
        "subject", "relation", "relation_category",
        "object", "article_number", "confidence", "concepts", "created_at"
    ]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for t in triplets:
            writer.writerow({
                "subject": t.subject,
                "relation": t.relation,
                "relation_category": t.relation_category or "",
                "object": t.object,
                "article_number": t.article_number,
                "confidence": t.confidence,
                "concepts": "|".join(t.concepts),
                "created_at": t.created_at,
            })
def export_nodes_tsv(entities: List[LegalEntity], filepath: str):
    """노드를 TSV로 저장"""
    fieldnames = [
        "article_number", "structural_index", "entity_type",
        "concept", "subject", "action", "object",
        "legal_force", "full_text"
    ]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for e in entities:
            writer.writerow({
                "article_number": e.article_number,
                "structural_index": str(e.structural_index),
                "entity_type": e.entity_type,
                "concept": e.concept,
                "subject": e.subject or "",
                "action": e.action or "",
                "object": e.object or "",
                "legal_force": e.legal_force or "",
                "full_text": e.full_text.replace("\n", " "),
            })
def export_triplets_tsv(triplets: List[GraphTriplet], filepath: str):
    """트리플을 TSV로 저장"""
    fieldnames = [
        "subject", "relation", "relation_category",
        "object", "article_number", "confidence", "concepts", "created_at"
    ]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for t in triplets:
            writer.writerow({
                "subject": t.subject,
                "relation": t.relation,
                "relation_category": t.relation_category or "",
                "object": t.object,
                "article_number": t.article_number,
                "confidence": t.confidence,
                "concepts": "|".join(t.concepts),
                "created_at": t.created_at,
            })
def export_summary_txt(document: LegalDocument, filepath: str):
    """노드+트리플 요약을 TXT로 저장"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"=== 법률 지식 그래프 추출 결과 ===\n")
        f.write(f"문서: {document.title}\n")
        f.write(f"생성일: {document.created_at}\n")
        f.write(f"추출된 노드: {len(document.entities)}개\n")
        f.write(f"추출된 트리플: {len(document.triplets)}개\n\n")
        f.write("=== NODES ===\n")
        for e in document.entities:
            f.write(f"[{e.article_number}] ({e.entity_type}) {e.concept}\n")
            f.write(f"  주체: {e.subject or '-'} | 행위: {e.action or '-'} | 대상: {e.object or '-'}\n")
            f.write(f"  강제성: {e.legal_force or '-'}\n")
            f.write(f"  원문: {e.full_text[:100].replace(chr(10), ' ')}...\n\n")
        f.write("=== TRIPLETS ===\n")
        for t in document.triplets:
            f.write(f"[{t.article_number}] {t.subject} --[{t.relation}]--> {t.object}  (confidence={t.confidence:.2f})\n")
def export_all(document: LegalDocument, base_name: Optional[str] = None) -> str:
    """노드와 트리플을 CSV, TSV, TXT 세 가지 형식으로 모두 저장.
    Returns:
        저장된 디렉토리 경로
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = base_name or document.doc_id or "output"
    # 파일명에 사용할 수 없는 문자 제거
    safe_base = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)
    out_dir = _make_output_dir(safe_base)
    export_nodes_csv(document.entities, os.path.join(out_dir, f"nodes_{timestamp}.csv"))
    export_triplets_csv(document.triplets, os.path.join(out_dir, f"triplets_{timestamp}.csv"))
    export_nodes_tsv(document.entities, os.path.join(out_dir, f"nodes_{timestamp}.tsv"))
    export_triplets_tsv(document.triplets, os.path.join(out_dir, f"triplets_{timestamp}.tsv"))
    export_summary_txt(document, os.path.join(out_dir, f"summary_{timestamp}.txt"))
    return out_dir

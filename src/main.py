import os
import sys
from dotenv import load_dotenv
from rich.console import Console

from models.schemas import LegalDocument
from graphs.legal_graph import LegalKnowledgeGraphWorkflow
from utils.common_utils import check_gpu, test_llm_connection, save_to_memgraph, display_result_tables

# 환경 변수 로드
load_dotenv()

console = Console()


def main():
    console.print("=" * 80, style="bold cyan")
    console.print("🏛️ Legal Knowledge Graph - Gemini & Memgraph Edition", style="bold cyan")
    console.print("=" * 80, style="bold cyan")
    
    # GPU 확인
    check_gpu()
    
    # LLM 연결 테스트
    if not test_llm_connection():
        sys.exit(1)
    
    # 예시 법률 문서
    sample_document = LegalDocument(
        doc_id="sample_pipa",
        title="개인정보 보호법",
        law_number="법률 제18583호",
        content="""
제1조(목적) 이 법은 개인정보의 처리 및 보호에 관한 사항을 정함으로써 개인의 자유와 권리를 보호하고, 나아가 개인의 존엄과 가치를 구현함을 목적으로 한다.

제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.
1. "개인정보"란 살아 있는 개인에 관한 정보로서 성명, 주민등록번호 및 영상 등을 통하여 개인을 알아볼 수 있는 정보를 말한다.  

제3조(개인정보 보호 원칙) ① 개인정보처리자는 개인정보의 처리 목적을 명확하게 하여야 하고 그 목적에 필요한 범위에서 최소한의 개인정보만을 적법하고 정당하게 수집하여야 한다.  
        """.strip()
    )
    
    # 워크플로우 실행
    console.print("\n🚀 법률 지식 그래프 생성 시작...", style="bold green")
    workflow = LegalKnowledgeGraphWorkflow()
    
    with console.status("[bold green]처리 중...", spinner="dots"):
        result = workflow.process(sample_document)
    
    # 결과 테이블 표시
    display_result_tables(result)
    
    # Memgraph에 저장 (기존 데이터 삭제)
    save_to_memgraph(result, clear_existing=True)
    
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("✨ 처리 완료!", style="bold green")
    console.print("=" * 80, style="bold cyan")


if __name__ == "__main__":
    main()

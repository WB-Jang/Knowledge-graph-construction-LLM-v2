import os
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from models.schemas import LegalDocument
from graphs.legal_graph import LegalKnowledgeGraphWorkflow
from database.memgraph_client import MemgraphClient
from llm.gemini_client import get_llm as gemini_llm
from llm.llama_client import get_llm as opensource_llm

# 환경 변수 로드
load_dotenv()

console = Console()


def check_gpu():
    """GPU 확인"""
    try:
        import torch
        if torch.cuda.is_available():
            console.print(f"✅ GPU 사용 가능:  {torch.cuda.get_device_name(0)}", style="bold green")
            console.print(f"   CUDA 버전: {torch.version.cuda}")
            console.print(f"   GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        else:
            console.print("⚠️ GPU를 사용할 수 없습니다.  CPU 모드로 실행됩니다.", style="bold yellow")
    except ImportError:  
        console.print("⚠️ PyTorch가 설치되지 않았습니다.", style="bold yellow")


def test_llm_connection():
    """LLM 연결 테스트"""
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    
    if use_local:
        console.print("\n🔍 로컬 LLM 연결 테스트 중...", style="bold blue")
    else:
        console.print("\n🔍 Gemini API 연결 테스트 중...", style="bold blue")
    
    try:
        llm = opensource_llm()
        result = llm.invoke("안녕하세요. 간단히 인사해주세요.")
        console.print(f"✅ LLM 응답: {result[:100]}...", style="green")
        return True
    except Exception as e:  
        console.print(f"❌ LLM 연결 실패: {e}", style="bold red")
        
        if not use_local:
            console.print("\n⚠️ Gemini API 설정을 확인하세요:", style="bold yellow")
            console.print(f"   GOOGLE_API_KEY: {'설정됨' if os.getenv('GOOGLE_API_KEY') else '미설정'}")
            console.print("\n💡 Google AI Studio에서 API 키 발급:")
            console.print("   https://makersuite.google.com/app/apikey")
        else:
            console.print("\n⚠️ llama-cpp API 설정을 확인하세요:", style="bold yellow")
            console.print(f"   API URL: {os.getenv('LLAMA_CPP_API_URL', 'Not set')}")
        
        return False


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
    
    # 결과 테이블 생성
    entity_table = Table(title=f"📊 추출된 개체 ({len(result.entities)}개)")
    entity_table.add_column("조항", style="cyan")
    entity_table.add_column("개념", style="magenta")
    entity_table.add_column("주체", style="green")
    entity_table.add_column("행위", style="yellow")
    
    for entity in result.entities[: 10]:  # 상위 10개만
        entity_table.add_row(
            entity.article_number,
            entity.concept[: 30],
            entity.subject or "-",
            entity.action or "-"
        )
    
    console.print(entity_table)
    
    # 관계 테이블
    relation_table = Table(title=f"🔗 추출된 관계 ({len(result.triplets)}개)")
    relation_table.add_column("주체", style="cyan")
    relation_table.add_column("관계", style="magenta")
    relation_table.add_column("대상", style="green")
    relation_table.add_column("신뢰도", style="yellow")
    
    for triplet in result.triplets[:10]:   # 상위 10개만
        relation_table.add_row(
            triplet.subject[:20],
            triplet.relation,
            triplet.object[:20],
            f"{triplet.confidence:.2f}"
        )
    
    console.print(relation_table)
    
    # Memgraph에 저장
    console.print("\n💾 Memgraph에 저장 중...", style="bold blue")
    try:
        mg_client = MemgraphClient()
        mg_client.clear_database()
        mg_client.create_indexes()
        mg_client.save_document(result)
        
        stats = mg_client.get_graph_statistics()
        console.print(f"✅ 저장 완료 - 문서:  {stats.get('documents', 0)}, "
                     f"조항: {stats.get('articles', 0)}, "
                     f"개체: {stats.get('entities', 0)}", style="bold green")
        
        console.print("\n🌐 Memgraph Lab에서 확인하세요:", style="bold cyan")
        console.print("   http://localhost:3000")
        
        mg_client.close()
    except Exception as e:
        console.print(f"⚠️ Memgraph 저장 실패: {e}", style="bold yellow")
    
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("✨ 처리 완료!", style="bold green")
    console.print("=" * 80, style="bold cyan")


if __name__ == "__main__":
    main()

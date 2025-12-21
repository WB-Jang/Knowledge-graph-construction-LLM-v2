"""PDF 파일을 읽어서 지식 그래프로 변환하는 스크립트"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from models.schemas import LegalDocument
from graphs.legal_graph import LegalKnowledgeGraphWorkflow
from database.memgraph_client import MemgraphClient
from llm.gemini_client import get_llm as gemini_llm
from llm.llama_client import get_llm as opensource_llm
from utils.pdf_processor import extract_text_from_pdf, get_pdf_metadata, list_pdf_files

# 환경 변수 로드
load_dotenv()

console = Console()

# PDF 파일 저장 디렉토리
PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pdfs")


def check_gpu():
    """GPU 확인"""
    try:
        import torch
        if torch.cuda.is_available():
            console.print(f"✅ GPU 사용 가능: {torch.cuda.get_device_name(0)}", style="bold green")
            console.print(f"   CUDA 버전: {torch.version.cuda}")
            console.print(f"   GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        else:
            console.print("⚠️ GPU를 사용할 수 없습니다. CPU 모드로 실행됩니다.", style="bold yellow")
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


def select_pdf_file():
    """사용자가 처리할 PDF 파일을 선택합니다."""
    # PDF 디렉토리 생성 (존재하지 않으면)
    os.makedirs(PDF_DIR, exist_ok=True)
    
    # PDF 파일 목록 가져오기
    pdf_files = list_pdf_files(PDF_DIR)
    
    if not pdf_files:
        console.print(f"\n❌ {PDF_DIR} 디렉토리에 PDF 파일이 없습니다.", style="bold red")
        console.print(f"\n📁 PDF 파일을 다음 경로에 넣어주세요:", style="bold yellow")
        console.print(f"   {os.path.abspath(PDF_DIR)}")
        console.print("\n예: data/pdfs/법률문서.pdf")
        return None
    
    # PDF 파일 목록 표시
    console.print(f"\n📁 발견된 PDF 파일 ({len(pdf_files)}개):", style="bold cyan")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("번호", style="cyan", width=6)
    table.add_column("파일명", style="green")
    table.add_column("페이지", style="yellow", width=8)
    
    for idx, pdf_path in enumerate(pdf_files, 1):
        metadata = get_pdf_metadata(pdf_path)
        filename = Path(pdf_path).name
        pages = metadata.get('pages', '?')
        table.add_row(str(idx), filename, str(pages))
    
    console.print(table)
    
    # 사용자 선택
    while True:
        try:
            choice = Prompt.ask(
                "\n처리할 PDF 파일 번호를 입력하세요",
                default="1"
            )
            choice_idx = int(choice) - 1
            
            if 0 <= choice_idx < len(pdf_files):
                return pdf_files[choice_idx]
            else:
                console.print("❌ 잘못된 번호입니다. 다시 입력해주세요.", style="bold red")
        except ValueError:
            console.print("❌ 숫자를 입력해주세요.", style="bold red")
        except KeyboardInterrupt:
            console.print("\n\n취소되었습니다.")
            return None


def process_pdf_document(pdf_path: str):
    """PDF 문서를 처리하여 지식 그래프를 생성합니다."""
    console.print(f"\n📄 PDF 파일 읽기 중: {Path(pdf_path).name}", style="bold blue")
    
    try:
        # PDF에서 텍스트 추출
        content = extract_text_from_pdf(pdf_path)
        metadata = get_pdf_metadata(pdf_path)
        
        console.print(f"✅ PDF 읽기 완료 - {len(content)} 문자, {metadata['pages']} 페이지", style="green")
        
        # 법률 문서 객체 생성
        title = metadata.get('title') or metadata.get('subject') or Path(pdf_path).stem
        
        document = LegalDocument(
            title=title,
            law_number=f"PDF 문서 - {Path(pdf_path).name}",
            content=content
        )
        
        # 워크플로우 실행
        console.print("\n🚀 법률 지식 그래프 생성 시작...", style="bold green")
        workflow = LegalKnowledgeGraphWorkflow()
        
        with console.status("[bold green]처리 중...", spinner="dots"):
            result = workflow.process(document)
        
        # 결과 출력
        console.print(f"\n✨ 처리 완료!", style="bold green")
        console.print(f"   추출된 조항: {len(result.entities)}개")
        console.print(f"   추출된 관계: {len(result.triplets)}개")
        
        # 결과 테이블 생성
        if result.entities:
            entity_table = Table(title=f"📊 추출된 개체 (상위 {min(10, len(result.entities))}개)")
            entity_table.add_column("조항", style="cyan")
            entity_table.add_column("개념", style="magenta")
            entity_table.add_column("주체", style="green")
            entity_table.add_column("행위", style="yellow")
            
            for entity in result.entities[:10]:
                entity_table.add_row(
                    entity.article_number,
                    entity.concept[:30],
                    entity.subject or "-",
                    entity.action or "-"
                )
            
            console.print(entity_table)
        
        # 관계 테이블
        if result.triplets:
            relation_table = Table(title=f"🔗 추출된 관계 (상위 {min(10, len(result.triplets))}개)")
            relation_table.add_column("주체", style="cyan")
            relation_table.add_column("관계", style="magenta")
            relation_table.add_column("대상", style="green")
            relation_table.add_column("신뢰도", style="yellow")
            
            for triplet in result.triplets[:10]:
                relation_table.add_row(
                    triplet.subject[:20],
                    triplet.relation,
                    triplet.object[:20],
                    f"{triplet.confidence:.2f}"
                )
            
            console.print(relation_table)
        
        # Memgraph에 저장 여부 확인
        if Confirm.ask("\n💾 결과를 Memgraph에 저장하시겠습니까?", default=True):
            save_to_memgraph(result)
        
        return result
        
    except FileNotFoundError as e:
        console.print(f"\n❌ {e}", style="bold red")
        return None
    except Exception as e:
        console.print(f"\n❌ PDF 처리 중 오류 발생: {e}", style="bold red")
        import traceback
        console.print(traceback.format_exc(), style="red")
        return None


def save_to_memgraph(document: LegalDocument):
    """처리된 문서를 Memgraph에 저장합니다."""
    console.print("\n💾 Memgraph에 저장 중...", style="bold blue")
    
    try:
        mg_client = MemgraphClient()
        
        # 기존 데이터 삭제 여부 확인
        if Confirm.ask("   기존 데이터를 삭제하시겠습니까?", default=False):
            mg_client.clear_database()
            console.print("   🗑️ 기존 데이터 삭제 완료", style="yellow")
        
        mg_client.create_indexes()
        mg_client.save_document(document)
        
        stats = mg_client.get_graph_statistics()
        console.print(f"✅ 저장 완료 - 문서: {stats.get('documents', 0)}, "
                     f"조항: {stats.get('articles', 0)}, "
                     f"개체: {stats.get('entities', 0)}", style="bold green")
        
        console.print("\n🌐 Memgraph Lab에서 확인하세요:", style="bold cyan")
        console.print("   http://localhost:3000")
        
        mg_client.close()
        
    except Exception as e:
        console.print(f"⚠️ Memgraph 저장 실패: {e}", style="bold yellow")


def main():
    """메인 함수"""
    console.print("=" * 80, style="bold cyan")
    console.print("📄 PDF Legal Knowledge Graph Processor", style="bold cyan")
    console.print("=" * 80, style="bold cyan")
    
    # GPU 확인
    check_gpu()
    
    # LLM 연결 테스트
    if not test_llm_connection():
        sys.exit(1)
    
    # PDF 파일 선택
    pdf_path = select_pdf_file()
    
    if not pdf_path:
        console.print("\n❌ PDF 파일을 선택하지 않았습니다.", style="bold red")
        sys.exit(1)
    
    # PDF 문서 처리
    result = process_pdf_document(pdf_path)
    
    if result:
        console.print("\n" + "=" * 80, style="bold cyan")
        console.print("✨ 모든 작업이 완료되었습니다!", style="bold green")
        console.print("=" * 80, style="bold cyan")
    else:
        console.print("\n❌ 처리 실패", style="bold red")
        sys.exit(1)


if __name__ == "__main__":
    main()

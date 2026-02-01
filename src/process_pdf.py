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
from utils.pdf_processor import extract_text_from_pdf, get_pdf_metadata, list_pdf_files
from utils.text_processor import clean_text, split_articles
from utils.common_utils import check_gpu, test_llm_connection, save_to_memgraph, display_result_tables

# 환경 변수 로드
load_dotenv()
print(os.getenv("GOOGLE_API_KEY"))
console = Console()

# PDF 파일 저장 디렉토리
PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pdfs")


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
        
        # text_processor를 사용하여 텍스트 정제 및 파싱
        content = clean_text(content)
        
        # split_articles를 사용하여 조항별로 분리하고 다시 결합
        # 이는 텍스트를 조항 단위로 정리하여 더 나은 파싱 결과를 제공합니다
        articles = split_articles(content)
        content = "\n\n".join(articles)  # 조항들을 개행으로 구분하여 재결합
        
        metadata = get_pdf_metadata(pdf_path)
        
        console.print(f"✅ PDF 읽기 완료 - {len(content)} 문자, {metadata['pages']} 페이지, {len(articles)} 조항", style="green")
        
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
        
        # 결과 테이블 표시
        display_result_tables(result)
        
        # Memgraph에 저장 여부 확인
        if Confirm.ask("\n💾 결과를 Memgraph에 저장하시겠습니까?", default=True):
            clear_existing = Confirm.ask("   기존 데이터를 삭제하시겠습니까?", default=False)
            save_to_memgraph(result, clear_existing=clear_existing)
        
        return result
        
    except FileNotFoundError as e:
        console.print(f"\n❌ {e}", style="bold red")
        return None
    except Exception as e:
        console.print(f"\n❌ PDF 처리 중 오류 발생: {e}", style="bold red")
        import traceback
        console.print(traceback.format_exc(), style="red")
        return None


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

"""Common utility functions for GPU checking, LLM connection testing, and Memgraph operations"""
import os
from rich.console import Console
from rich.table import Table
# from typing import Optional

from models.schemas import LegalDocument

console = Console()


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


def test_llm_connection() -> bool:
    """LLM 연결 테스트"""
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"

    if use_local:
        console.print("\n🔍 로컬 LLM 연결 테스트 중...", style="bold blue")
        from llm.llama_client import get_llm as get_llm_fn
    else:
        console.print("\n🔍 ��용 API 연결 테스트 중...", style="bold blue")
        from llm.llm_client import get_llm as get_llm_fn  # 'llm' 이름 충돌 제거

    try:
        llm_instance = get_llm_fn('openrouter')
        from langchain_core.messages import HumanMessage
        result = llm_instance.invoke([HumanMessage(content="안녕하세요. 간단히 인사해주세요.")])

        # AIMessage 객체인 경우 content 속성 사용
        if hasattr(result, 'content'):
            response_text = result.content
        else:
            response_text = str(result)

        # 응답이 너무 길면 자르기
        model_nm=os.getenv('OPENROUTER_MODEL')
        display_text = response_text[:100] + "..." if len(response_text) > 100 else response_text
        console.print(f"✅ LLM({model_nm}) 응답: {display_text}", style="green")
        return True
    except Exception as e:
        console.print(f"❌ LLM 연결 실패: {e}", style="bold red")

        if not use_local:
            provider = os.getenv("LLM_PROVIDER", "groq").lower()
            if provider == "openrouter":
                console.print("\n⚠️ OpenRouter API 설정을 확인하세요:", style="bold yellow")
                console.print(f"   OPENROUTER_API_KEY: {'설정됨' if os.getenv('OPENROUTER_API_KEY') else '미설정'}")
                console.print("\n💡 OpenRouter에서 API 키 발급:")
                console.print("   https://openrouter.ai/keys")
            elif provider == "groq":
                console.print("\n⚠️ Groq API 설정을 확인하세요:", style="bold yellow")
                console.print(f"   GROQ_API_KEY: {'설정됨' if os.getenv('GROQ_API_KEY') else '미설정'}")
            else:
                console.print("\n⚠️ Gemini API 설정을 확인하세요:", style="bold yellow")
                console.print(f"   GOOGLE_API_KEY: {'설정됨' if os.getenv('GOOGLE_API_KEY') else '미설정'}")
                console.print("\n💡 Google AI Studio에서 API 키 발급:")
                console.print("   https://makersuite.google.com/app/apikey")
        else:
            console.print("\n⚠️ llama-cpp API 설정을 확인하세요:", style="bold yellow")
            console.print(f"   API URL: {os.getenv('LLAMA_CPP_API_URL', 'Not set')}")

        return False

# def test_llm_connection() -> bool:
#     """LLM 연결 테스트"""
#     use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    
#     if use_local:
#         console.print("\n🔍 로컬 LLM 연결 테스트 중...", style="bold blue")
#         from llm.llama_client import get_llm as opensource_llm
#         llm_getter = opensource_llm
#     else:
#         console.print("\n🔍 상용 API 연결 테스트 중...", style="bold blue")
#         from llm.llm_client import get_llm as get_llm_fn
#         llm_getter = get_llm_fn('openrouter')
    
#     try:
#         llm = llm_getter()
#         result = llm.invoke("안녕하세요. 간단히 인사해주세요.")
        
#         # AIMessage 객체인 경우 content 속성 사용
#         if hasattr(result, 'content'):
#             response_text = result.content
#         else:
#             response_text = str(result)
        
#         # 응답이 너무 길면 자르기
#         display_text = response_text[:100] + "..." if len(response_text) > 100 else response_text
#         console.print(f"✅ LLM 응답: {display_text}", style="green")
#         return True
#     except Exception as e:
#         console.print(f"❌ LLM 연결 실패: {e}", style="bold red")
        
#         if not use_local:
#             console.print("\n⚠️ Gemini API 설정을 확인하세요:", style="bold yellow")
#             console.print(f"   GOOGLE_API_KEY: {'설정됨' if os.getenv('GOOGLE_API_KEY') else '미설정'}")
#             console.print("\n💡 Google AI Studio에서 API 키 발급:")
#             console.print("   https://makersuite.google.com/app/apikey")
#         else:
#             console.print("\n⚠️ llama-cpp API 설정을 확인하세요:", style="bold yellow")
#             console.print(f"   API URL: {os.getenv('LLAMA_CPP_API_URL', 'Not set')}")
        
#         return False


def save_to_memgraph(document: LegalDocument, clear_existing: bool = False):
    """처리된 문서를 Memgraph에 저장합니다.
    
    Args:
        document: 저장할 법률 문서
        clear_existing: 기존 데이터 삭제 여부
    """
    # Import MemgraphClient here to avoid circular imports
    from database.memgraph_client import MemgraphClient
    
    console.print("\n💾 Memgraph에 저장 중...", style="bold blue")
    
    mg_client = None
    try:
        mg_client = MemgraphClient()
        
        if clear_existing:
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
        
    except Exception as e:
        console.print(f"⚠️ Memgraph 저장 실패: {e}", style="bold yellow")
    finally:
        if mg_client:
            mg_client.close()


def display_result_tables(result: LegalDocument, max_items: int = 10):
    """처리 결과를 테이블 형태로 출력합니다.
    
    Args:
        result: 처리된 법률 문서
        max_items: 출력할 최대 항목 수
    """
    # 개체 테이블
    if result.entities:
        entity_table = Table(title=f"📊 추출된 개체 (상위 {min(max_items, len(result.entities))}개)")
        entity_table.add_column("조항", style="cyan")
        entity_table.add_column("개념", style="magenta")
        entity_table.add_column("주체", style="green")
        entity_table.add_column("행위", style="yellow")
        
        for entity in result.entities[:max_items]:
            entity_table.add_row(
                entity.article_number,
                (entity.concept or "-")[:30],  # None 방어 처리
                entity.subject or "-",
                entity.action or "-"
            )
        
        console.print(entity_table)
    
    # 관계 테이블
    if result.triplets:
        relation_table = Table(title=f"🔗 추출된 관계 (상위 {min(max_items, len(result.triplets))}개)")
        relation_table.add_column("주체", style="cyan")
        relation_table.add_column("관계", style="magenta")
        relation_table.add_column("대상", style="green")
        relation_table.add_column("신뢰도", style="yellow")
        
        for triplet in result.triplets[:max_items]:
            relation_table.add_row(
                triplet.subject[:20],
                triplet.relation,
                triplet.object[:20],
                f"{triplet.confidence:.2f}"
            )
        
        console.print(relation_table)

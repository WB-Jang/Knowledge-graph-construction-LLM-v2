"""PDF 문서 처리 유틸리티"""
import os
from typing import Optional
import fitz  # PyMuPDF
from pathlib import Path


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    PDF 파일에서 텍스트를 추출합니다.
    
    Args:
        pdf_path: PDF 파일 경로
        
    Returns:
        추출된 텍스트
        
    Raises:
        FileNotFoundError: PDF 파일이 존재하지 않을 때
        Exception: PDF 읽기 실패 시
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
    
    try:
        # PyMuPDF로 PDF 열기
        doc = fitz.open(pdf_path)
        text_content = []
        
        # 각 페이지에서 텍스트 추출
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_content.append(text)
        
        doc.close()
        
        # 전체 텍스트 결합
        full_text = "\n\n".join(text_content)
        return full_text.strip()
        
    except Exception as e:
        raise Exception(f"PDF 읽기 실패: {str(e)}")


def get_pdf_metadata(pdf_path: str) -> dict:
    """
    PDF 파일의 메타데이터를 추출합니다.
    
    Args:
        pdf_path: PDF 파일 경로
        
    Returns:
        메타데이터 딕셔너리 (title, author, pages 등)
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
    
    try:
        doc = fitz.open(pdf_path)
        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "pages": len(doc),
            "filename": Path(pdf_path).name
        }
        doc.close()
        return metadata
        
    except Exception as e:
        return {
            "title": "",
            "author": "",
            "subject": "",
            "pages": 0,
            "filename": Path(pdf_path).name,
            "error": str(e)
        }


def list_pdf_files(directory: str) -> list:
    """
    디렉토리 내의 모든 PDF 파일을 나열합니다.
    
    Args:
        directory: 검색할 디렉토리 경로
        
    Returns:
        PDF 파일 경로 리스트
    """
    pdf_files = []
    
    if not os.path.exists(directory):
        return pdf_files
    
    for file in os.listdir(directory):
        if file.lower().endswith('.pdf'):
            pdf_files.append(os.path.join(directory, file))
    
    return sorted(pdf_files)

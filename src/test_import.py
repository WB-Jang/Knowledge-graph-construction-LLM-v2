#!/usr/bin/env python3
"""임포트 테스트 스크립트"""

print("1. dotenv 임포트 중...")
from dotenv import load_dotenv
load_dotenv()
print("   ✅ dotenv OK")

print("2. 기본 모듈 임포트 중...")
from models.schemas import LegalDocument
print("   ✅ schemas OK")

print("3. utils 임포트 중...")
from utils.pdf_processor import list_pdf_files
print("   ✅ pdf_processor OK")

print("4. common_utils 임포트 중...")
from utils.common_utils import check_gpu
print("   ✅ common_utils OK")

print("5. legal_graph 임포트 중...")
from graphs.legal_graph import LegalKnowledgeGraphWorkflow
print("   ✅ legal_graph OK")

print("\n모든 임포트 성공!")

print("\n6. GPU 체크 실행중...")
check_gpu()

print("\n7. PDF 파일 목록 확인...")
import os
PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pdfs")
pdfs = list_pdf_files(PDF_DIR)
print(f"   발견된 PDF: {len(pdfs)}개")

print("\n✅ 모든 테스트 통과!")

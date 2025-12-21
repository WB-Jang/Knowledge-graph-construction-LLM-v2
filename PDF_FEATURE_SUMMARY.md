# PDF Processing Feature - Summary

## 요약

사용자 요청에 따라 **실제 PDF 파일을 처리할 수 있는 기능**을 추가했습니다. 이제 mocking 데이터가 아닌 실제 법률 문서 PDF를 넣어서 바로 실행할 수 있습니다.

## 추가된 기능

### 1. PDF 처리 유틸리티 (`src/utils/pdf_processor.py`)
- `extract_text_from_pdf()`: PDF에서 텍스트 자동 추출
- `get_pdf_metadata()`: PDF 메타데이터 (제목, 저자, 페이지 수) 추출
- `list_pdf_files()`: 디렉토리 내 PDF 파일 목록 조회

### 2. 대화형 PDF 처리 스크립트 (`src/process_pdf.py`)
- PDF 파일 자동 검색 및 선택
- 텍스트 추출 및 지식 그래프 생성
- 결과를 테이블로 시각화
- Memgraph 저장 옵션 (선택적)

### 3. 디렉토리 구조
```
data/pdfs/              ← PDF 파일을 여기에 저장
├── README.md           ← 상세 가이드
└── (법률문서.pdf)      ← 사용자가 추가할 PDF
```

### 4. 문서 및 가이드
- `README.md` 업데이트: PDF 처리 섹션 추가
- `PDF_사용_가이드.md`: 전체 사용 가이드
- `data/pdfs/README.md`: PDF 디렉토리 가이드

### 5. 테스트
- `tests/test_pdf_processor.py`: PDF 처리 유틸리티 테스트 (5개 테스트)
- 모든 테스트 통과 (56개 테스트)

## 사용 방법

### 간단한 사용
```bash
# 1. PDF 파일 복사
cp ~/Downloads/법률문서.pdf data/pdfs/

# 2. 스크립트 실행
python src/process_pdf.py

# 3. 화면의 안내에 따라 진행
```

### 실행 과정
1. GPU/LLM 연결 확인
2. `data/pdfs/` 디렉토리의 PDF 목록 표시
3. 처리할 파일 번호 입력
4. 자동으로 텍스트 추출 및 분석
5. 결과 표시 (개체, 관계)
6. Memgraph 저장 여부 선택

## 기술 스택

- **PDF 처리**: PyMuPDF (fitz)
- **백업 라이브러리**: pypdf2
- **대화형 UI**: rich (Console, Table, Prompt)
- **기존 기능**: LangChain, LangGraph, Gemini/Llama LLM

## 지원 사항

✅ **지원:**
- 텍스트 PDF 파일
- 한글/영문 법률 문서
- 여러 PDF 파일 순차 처리

❌ **미지원 (향후 추가 가능):**
- 스캔 이미지 PDF (OCR 필요)
- 암호화된 PDF

## Commits

1. `5136e24` - Add PDF file processing capability with interactive script
2. `1172a81` - Add data/pdfs/README.md guide and update .gitignore

## 다음 단계 (선택사항)

사용자가 원할 경우:
1. OCR 기능 추가 (이미지 PDF 지원)
2. 배치 처리 모드 (여러 PDF 자동 처리)
3. 웹 인터페이스 추가
4. PDF 품질 검증 기능

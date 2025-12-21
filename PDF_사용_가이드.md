# PDF 파일 처리 가이드

## 📄 개요

이제 실제 PDF 파일을 넣어서 법률 지식 그래프를 생성할 수 있습니다!

## 🚀 사용 방법

### 1단계: PDF 파일 준비

PDF 파일을 `data/pdfs/` 디렉토리에 복사합니다:

```bash
# 프로젝트 루트 디렉토리에서
cp /path/to/your/법률문서.pdf data/pdfs/
```

**예시:**
```bash
cp ~/Downloads/개인정보보호법.pdf data/pdfs/
cp ~/Downloads/저작권법.pdf data/pdfs/
```

### 2단계: PDF 처리 스크립트 실행

```bash
# 프로젝트 루트 디렉토리에서
python src/process_pdf.py

# 또는 poetry 사용 시
poetry run python src/process_pdf.py
```

### 3단계: 대화형 처리

스크립트를 실행하면 다음과 같은 과정이 진행됩니다:

1. **GPU/LLM 연결 확인**
   - GPU 사용 가능 여부 확인
   - Gemini API 또는 로컬 LLM 연결 테스트

2. **PDF 파일 선택**
   ```
   📁 발견된 PDF 파일 (3개):
   ┌──────┬─────────────────────┬────────┐
   │ 번호 │ 파일명               │ 페이지 │
   ├──────┼─────────────────────┼────────┤
   │ 1    │ 개인정보보호법.pdf   │ 45     │
   │ 2    │ 저작권법.pdf         │ 38     │
   │ 3    │ 특허법.pdf           │ 52     │
   └──────┴─────────────────────┴────────┘
   
   처리할 PDF 파일 번호를 입력하세요 [1]:
   ```

3. **자동 처리**
   - PDF에서 텍스트 자동 추출
   - 법률 조항 분석
   - 개체 및 관계 추출
   - 지식 그래프 생성

4. **결과 확인**
   ```
   📊 추출된 개체 (10개)
   ┌────────┬──────────────┬────────┬────────┐
   │ 조항   │ 개념          │ 주체    │ 행위    │
   ├────────┼──────────────┼────────┼────────┤
   │ 제1조  │ 목적          │ 법      │ 정의함  │
   ...
   
   🔗 추출된 관계 (15개)
   ┌────────┬────────┬────────┬────────┐
   │ 주체   │ 관계    │ 대상    │ 신뢰도 │
   ├────────┼────────┼────────┼────────┤
   │ 법     │ 정의함  │ 목적    │ 0.95   │
   ...
   ```

5. **Memgraph 저장 (선택)**
   ```
   💾 결과를 Memgraph에 저장하시겠습니까? [Y/n]:
   
   기존 데이터를 삭제하시겠습니까? [y/N]:
   ```

## 📝 지원되는 PDF 파일

✅ **지원:**
- 텍스트가 포함된 PDF 파일
- 한글/영문 법률 문서
- 일반적인 법률 조항 구조

❌ **미지원 (현재):**
- 스캔된 이미지 PDF (OCR 필요)
- 복잡한 레이아웃의 PDF
- 암호화된 PDF

## 🔧 설정

### .env 파일 설정

```bash
# Gemini API 사용 (권장)
GOOGLE_API_KEY=your-api-key-here
GEMINI_MODEL=gemini-2.5-flash-preview-09-2025

# 또는 로컬 LLM 사용
USE_LOCAL_LLM=true
LLAMA_CPP_API_URL=http://localhost:8000
```

### 의존성 설치

```bash
# PDF 처리 라이브러리
pip install PyMuPDF pypdf2

# 또는 poetry
poetry add PyMuPDF pypdf2
```

## 📂 디렉토리 구조

```
Knowledge-graph-construction-LLM-v2/
├── data/
│   └── pdfs/              ← 여기에 PDF 파일 저장
│       ├── README.md      ← 상세 가이드
│       ├── 개인정보보호법.pdf
│       ├── 저작권법.pdf
│       └── 특허법.pdf
├── src/
│   ├── process_pdf.py     ← PDF 처리 메인 스크립트
│   └── utils/
│       └── pdf_processor.py  ← PDF 처리 유틸리티
└── ...
```

## 💡 팁

1. **대용량 PDF 처리**
   - 페이지 수가 많은 PDF는 처리 시간이 오래 걸릴 수 있습니다
   - Gemini API 사용 시 더 빠르게 처리됩니다

2. **여러 파일 처리**
   - 스크립트를 여러 번 실행하여 여러 파일을 처리할 수 있습니다
   - Memgraph 저장 시 "기존 데이터 삭제" 옵션을 조정하세요

3. **결과 확인**
   - Memgraph Lab: http://localhost:3000
   - Cypher 쿼리로 결과를 탐색할 수 있습니다

## 🐛 문제 해결

### PDF 읽기 실패
```bash
❌ PDF 읽기 실패: ...
```
- PDF 파일이 손상되었거나 암호화되어 있을 수 있습니다
- 다른 PDF 뷰어로 열어보세요

### LLM 연결 실패
```bash
❌ LLM 연결 실패: ...
```
- `.env` 파일의 API 키를 확인하세요
- Gemini API: https://makersuite.google.com/app/apikey
- 로컬 LLM: llama-cpp 서버가 실행 중인지 확인

### Memgraph 연결 실패
```bash
⚠️ Memgraph 저장 실패: ...
```
- Memgraph 서버가 실행 중인지 확인하세요
- Docker: `docker-compose up -d memgraph`

## 📞 도움말

더 자세한 내용은 다음을 참고하세요:
- [README.md](../README.md) - 전체 프로젝트 가이드
- [TEST_REPORT.md](../TEST_REPORT.md) - 테스트 결과
- [data/pdfs/README.md](../data/pdfs/README.md) - PDF 디렉토리 가이드

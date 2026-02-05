# Legal Knowledge Graph v2 🏛️
## GPU & Memgraph & Llama-cpp Edition

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/WB-Jang/Knowledge-graph-construction-LLM-v2/blob/main/knowledge_graph_colab.ipynb)

한국어 법률 문서를 오픈소스 LLM과 Memgraph를 활용하여 지식그래프로 변환하는 프로젝트

## 🎯 주요 기능

- **GPU 가속 지원** (NVIDIA CUDA 12.1)
- **Memgraph 그래프 데이터베이스**
- **외부 llama-cpp API 연동**
- **2단계 추출 방식**
  - Step 1: 조항별 구조화 및 개체 추출
  - Step 2: 관계 정의 (Graph Triplets)
- **LangChain & LangGraph 워크플로우**

## 🏗️ 프로젝트 구조

```
├── data/
│   └── pdfs/               # PDF 파일 저장 디렉토리
├── src/
│   ├── llm/                # LLM 클라이언트
│   │   ├── llama_client.py
│   │   └── gemini_client.py
│   ├── chains/             # LangChain 체인(node / relation extractor)
│   ├── graphs/             # LangGraph 워크플로우
│   ├── database/           # Memgraph 클라이언트
│   ├── models/             # Pydantic 스키마(node / relation 사전 정의 스키마)
│   ├── utils/              # 유틸리티
│   │   ├── text_processor.py
│   │   └── pdf_processor.py  # PDF 처리
│   ├── main.py             # 예제 실행 스크립트
│   └── process_pdf.py      # PDF 처리 스크립트
├── Docker-compose.yml      # Docker-compse
└── Dockerfile              # GPU Docker 설정
```


### 🐳 로컬 환경 또는 Docker에서 전체 기능 사용하기

전체 기능(Memgraph, 무제한 조항 처리 등)을 사용하려면 로컬 환경이나 Docker를 사용하세요.

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
poetry install
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


## 📊 Memgraph Lab

- **URL**: http://localhost:3000
- **Bolt**:  bolt://localhost:7687

### 쿼리 예시

```cypher
// 모든 문서 조회
MATCH (d:Document) RETURN d;

// 특정 조항 조회
MATCH (a:Article {number: "제1조"}) RETURN a;

// 조항 간 관계 시각화
MATCH (a: Article)-[:HAS_RELATION]->(r)->(e:Entity)
RETURN a, r, e LIMIT 50;

// 가장 많이 참조되는 개체
MATCH (e:Entity)<-[r: RELATION]-()
RETURN e. name, count(r) as refs
ORDER BY refs DESC LIMIT 10;
```


## 🔧 개발

```bash
# 의존성 추가
poetry add package-name

# GPU 확인
poetry run python -c "import torch; print(torch. cuda.is_available())"

# 테스트
poetry run pytest

# 코드 포매팅
poetry run black src/
poetry run isort src/
```

## 🤖 지원하는 LLM

외부 llama-cpp 서버를 통해 다음 모델들을 사용할 수 있습니다:

- **한국어 모델**
  - beomi/Llama-3-Open-Ko-8B
  - yanolja/EEVE-Korean-10. 8B
  - maywell/EXAONE-3.0-7. 8B-Instruct

- **다국어 모델**
  - meta-llama/Llama-3.1-8B-Instruct
  - mistralai/Mistral-7B-Instruct-v0.3

## 📈 성능 최적화

```bash
# GPU 메모리 최적화
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# Memgraph 메모리 설정 (docker-compose. yml)
command: ["--memory-limit=8192"]
```

## 🐛 트러블슈팅

### GPU 인식 안됨
```bash
# NVIDIA 드라이버 확인
nvidia-smi

# Docker GPU 런타임 확인
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### llama-cpp API 연결 실패
```bash
# API 서버 상태 확인
curl http://localhost:8000/v1/models

# Docker 내부에서 호스트 접근
# . env에서 LLAMA_CPP_API_URL=http://host.docker.internal:8000
```

### Memgraph 연결 실패
```bash
# Memgraph 상태 확인
docker-compose ps memgraph

# 로그 확인
docker-compose logs memgraph
```

## 📄 라이선스

MIT License
```

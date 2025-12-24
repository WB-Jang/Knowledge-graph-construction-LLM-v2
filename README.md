# Legal Knowledge Graph v2🏛️
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

## 🚀 시작하기

### 🌐 Google Colab에서 빠르게 시작하기 (권장)

Docker나 로컬 환경 설정 없이 Google Colab에서 바로 실행할 수 있습니다!

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/WB-Jang/Knowledge-graph-construction-LLM-v2/blob/main/knowledge_graph_colab.ipynb)

**Colab 노트북 특징:**
- ✅ 무료 GPU (T4) 사용 가능
- ✅ Google Gemini API 연동 (무료 tier)
- ✅ PDF 파일 업로드 및 처리
- ✅ 결과 시각화 및 다운로드
- ✅ 환경 설정 불필요

**사용 방법:**
1. 위 배지를 클릭하여 Colab 노트북 열기
2. Google Gemini API 키 발급 ([API 키 받기](https://makersuite.google.com/app/apikey))
3. 노트북의 셀을 순차적으로 실행
4. 샘플 법률 텍스트 또는 PDF 파일 처리

> 💡 **참고:** Colab 환경에서는 Memgraph를 사용하지 않고 메모리 기반으로 처리하며, 테스트 목적으로 처음 3개 조항만 처리합니다.

---

### 🐳 로컬 환경 또는 Docker에서 전체 기능 사용하기

전체 기능(Memgraph, 무제한 조항 처리 등)을 사용하려면 로컬 환경이나 Docker를 사용하세요.

### 전제 조건

1. **NVIDIA GPU & Docker GPU 지원**
   ```bash
   # NVIDIA Docker 설치
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
     sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   
   sudo apt-get update && sudo apt-get install -y nvidia-docker2
   sudo systemctl restart docker
   ```

2. **llama-cpp-python 서버 (외부에서 실행)**
   ```bash
   # llama-cpp-python 설치
   CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python[server]
   
   # 모델 다운로드 (예시)
   huggingface-cli download beomi/Llama-3-Open-Ko-8B-gguf
   
   # 서버 실행
   python -m llama_cpp.server \
     --model models/llama-3-open-ko-8b.Q4_K_M.gguf \
     --host 0.0.0.0 \
     --port 8000 \
     --n_gpu_layers 35 \
     --n_ctx 4096
   ```

### 1.  환경 설정

```bash
# 저장소 클론
git clone <your-repo>
cd legal-knowledge-graph

# 환경 변수 설정
cp .env.example .env
# . env 파일 수정
```

**.env 설정 예시:**
```bash
LLAMA_CPP_API_URL=http://host.docker.internal:8000
LLM_MODEL_NAME=llama-3-korean-8b
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=2048

MEMGRAPH_HOST=memgraph
MEMGRAPH_PORT=7687
```

### 2. Docker Compose로 실행

```bash
# GPU 확인
nvidia-smi

# 컨테이너 빌드 및 실행
docker-compose up -d --build

# 로그 확인
docker-compose logs -f legal-kg

# GPU 사용 확인
docker exec legal-knowledge-graph check-gpu
```

### 3. VSCode Dev Container 사용

1. VSCode에서 프로젝트 열기
2. `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"
3. 자동으로 GPU 환경 구성

### 4. 실행

#### 예제 코드로 실행 (기본)
```bash
# 컨테이너 내부에서
poetry run python src/main.py
```

#### PDF 파일로 실행
```bash
# 1. PDF 파일을 data/pdfs/ 디렉토리에 복사
cp /path/to/your/법률문서.pdf data/pdfs/

# 2. PDF 처리 스크립트 실행
poetry run python src/process_pdf.py
```

**PDF 처리 과정:**
1. `data/pdfs/` 디렉토리의 PDF 파일 목록이 표시됩니다
2. 처리할 파일 번호를 선택합니다
3. PDF에서 텍스트를 자동으로 추출합니다
4. 법률 조항을 분석하고 지식 그래프를 생성합니다
5. Memgraph에 저장할지 선택합니다

**참고:** PDF 파일은 텍스트가 포함된 파일이어야 합니다. 스캔된 이미지 PDF는 현재 지원하지 않습니다.

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

## 🏗️ 프로젝트 구조

```
├── src/
│   ├── llm/                # LLM 클라이언트
│   │   ├── llama_client.py
│   │   └── gemini_client.py
│   ├── chains/             # LangChain 체인
│   ├── graphs/             # LangGraph 워크플로우
│   ├── database/           # Memgraph 클라이언트
│   ├── models/             # Pydantic 스키마
│   ├── utils/              # 유틸리티
│   │   ├── text_processor.py
│   │   └── pdf_processor.py  # PDF 처리
│   ├── main.py             # 예제 실행 스크립트
│   └── process_pdf.py      # PDF 처리 스크립트
├── data/
│   └── pdfs/               # PDF 파일 저장 디렉토리
├── tests/                  # 테스트 파일
├── models/                 # 로컬 LLM 모델 (마운트)
└── Dockerfile              # GPU Docker 설정
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

## 🤝 기여

이슈와 PR을 환영합니다! 

## 📄 라이선스

MIT License
```

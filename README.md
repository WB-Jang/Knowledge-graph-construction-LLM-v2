# Legal Knowledge Graph v2 🏛️
## Generator–Evaluator–Reflection Edition

한국어 법률 문서를 LLM과 Memgraph를 활용하여 **고품질** 지식 그래프로 변환하는 프로젝트입니다.

문서가 입력되면 초소형 LLM이 Markdown으로 정규화하고, 단순·결정론적 파싱을 거쳐
생성 모델이 노드/트리플을 만들고, 평가 모델이 실시간으로 품질(완전성·충실성)을
판정하여 부족하면 조항 단위로 재생성하는 **다중 모델 반영(Reflection) 루프**가 핵심입니다.

---

## 🏗️ 파이프라인 아키텍처 (v2)

```
Document(PDF) 입력
  │
  ├─ [A] Formatter LLM (mistral-nemo)
  │       PDF 원문 → Markdown 정규화 (## 제N조 헤딩)
  │       ※ 출력이 원문의 80% 미만이면 원문 그대로 폴백 (truncation 방지)
  │
  ├─ [B] 단순 파싱 (split_markdown_articles)
  │       State Machine 파서: 장(章)/절(節)/조(條) 추적 → structural_index 산출
  │       부칙(附則)은 back_raw로 격리 (본문 오염 방지)
  │       ※ Markdown 헤딩이 없으면 정규식 파서로 자동 폴백
  │
  └─ 조항(Article) 단위 루프 ──────────────────────────────────┐
        │                                                      │
        ├─ [C] Generator LLM (gemma-4-26b-a4b-it)              │
        │       노드(LegalEntity) + 트리플(GraphTriplet) 생성  │
        │       ※ article_number·structural_index는 파서 값으로 │
        │         덮어써 환각 방지                              │
        │                                                      │
        ├─ [D] 규칙 기반 검증 (rule_validator, 무비용)         │
        │       조항번호 형식·관계 enum·명사구 길이·자기참조·   │
        │       빈 값·신뢰도 범위 검사 → 위반 트리플 필터링     │
        │                                                      │
        ├─ [E] Evaluator LLM (deepseek-v4-flash, 전수 평가)    │
        │       완전성(0~5) + 충실성(0~5) 채점 → PASS/FAIL     │
        │                                                      │
        ├─ PASS → 트리플 수집 ─────────────────────────────────┤
        │                                                      │
        └─ FAIL → 피드백 주입 후 재생성 (max_retries=3) ───────┘
                  └─ 3회 초과 실패 시 Dead Letter Queue(DLQ)로 격리
                       data/output/dead_letter_queue.csv

  → 전역 중복 제거(validate_graph)
  → Memgraph 저장 + pipeline 버전 속성 부여
  → CSV/TSV/TXT export
```

### 버전 추적 (pipeline versioning)

업그레이드된 코드로 생성한 그래프 데이터를 별도로 구분할 수 있도록,
모든 노드·엣지·문서에 다음 메타데이터를 부여합니다. Memgraph와 CSV/TSV
export 양쪽에 기록됩니다.

| 속성 | 설명 |
| --- | --- |
| `pipeline_version` | 파이프라인 버전 (기본 `2.0`) |
| `generator_model` | 노드·트리플 생성 모델 ID |
| `evaluator_model` | 품질 평가 모델 ID |
| `eval_score` | 평가 점수 (0.0~1.0) |
| `retry_count` | 재생성 시도 횟수 |

```cypher
// 예: v2 파이프라인으로 생성된 트리플만 조회
MATCH (s:Entity)-[r:RELATION {pipeline_version: "2.0"}]->(o:Entity)
RETURN s.name, r.type, o.name, r.eval_score
ORDER BY r.eval_score DESC;
```

---

## 🤖 사용 모델 (OpenRouter)

세 가지 역할 모두 OpenRouter 단일 프로바이더를 사용합니다. `.env`에서 변경 가능합니다.

| 역할 | 환경변수 | 기본 모델 |
| --- | --- | --- |
| Formatter | `FORMATTER_MODEL` | `mistralai/mistral-nemo` |
| Generator | `GENERATOR_MODEL` | `google/gemma-4-26b-a4b-it` |
| Evaluator | `EVALUATOR_MODEL` | `deepseek/deepseek-v4-flash` |

---

## 🚀 로컬에서 빠르게 실행하기 (Docker 불필요)

OpenRouter API만 있으면 GPU·Docker 없이 CPU 환경에서 바로 실행할 수 있습니다.

### 1. 클론 및 가상환경 설정

```bash
git clone https://github.com/WB-Jang/Knowledge-graph-construction-LLM-v2.git
cd Knowledge-graph-construction-LLM-v2

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

> 💡 `requirements.txt`는 OpenRouter 단일 프로바이더 기준 최소 의존성입니다.
> Groq·Gemini 등 다른 프로바이더나 GPU 확인이 필요하면 `requirements-optional.txt`를 추가 설치하세요.

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

`.env`에서 **최소한** 다음 두 가지만 설정하면 동작합니다:

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...        # https://openrouter.ai/keys 에서 발급

# (선택) 모델 변경 시
FORMATTER_MODEL=mistralai/mistral-nemo
GENERATOR_MODEL=google/gemma-4-26b-a4b-it
EVALUATOR_MODEL=deepseek/deepseek-v4-flash

# (선택) 반영 루프 파라미터
MAX_RETRIES=3
EVAL_PASS_THRESHOLD=0.7
```

> ℹ️ Memgraph가 없어도 실행됩니다. 저장 단계는 건너뛰거나(프롬프트에서 N 선택)
> 실패해도 경고만 출력하며, 결과는 항상 `data/output/`에 CSV/TSV/TXT로 저장됩니다.

### 3. 실행

스크립트는 `from models.schemas import ...` 형태의 임포트를 사용하므로
반드시 **`src/` 디렉터리 안에서** 실행해야 합니다.

#### (A) 샘플 텍스트로 빠르게 검증

```bash
cd src
python main.py
```

내장된 짧은 샘플(개인정보 보호법 일부)로 전체 파이프라인을 한 번 돌려봅니다.
API 연결·모델 응답·생성/평가 루프가 정상 동작하는지 확인하는 용도입니다.

#### (B) 실제 PDF 처리

```bash
# 1) PDF를 data/pdfs/ 에 복사
cp /path/to/법률문서.pdf data/pdfs/

# 2) 처리 스크립트 실행 (src 디렉터리 안에서)
cd src
python process_pdf.py
```

실행하면:
1. `data/pdfs/`의 PDF 목록이 표시됩니다 → 번호로 선택
2. 텍스트 추출 → Formatter → 파싱 → 생성/평가 루프가 진행됩니다
3. 콘솔에 조항별 `[eval]` PASS/FAIL과 점수가 출력됩니다
4. Memgraph 저장 여부를 묻습니다 (없으면 N)
5. 결과가 `data/output/<doc_id>_<timestamp>/`에 저장됩니다

> ⚠️ 텍스트가 포함된 PDF여야 합니다. 스캔 이미지 PDF는 현재 미지원입니다.
> ⚠️ 전수 평가(no sampling) 구조라 조항 수만큼 평가 모델 호출이 발생합니다.
> 조항이 많은 문서는 시간·비용이 늘어날 수 있습니다.

### 4. 결과 확인

```
data/output/<doc_id>_<timestamp>/
├── nodes_<ts>.csv / .tsv        # 노드 + pipeline 메타데이터 컬럼
├── triplets_<ts>.csv / .tsv     # 트리플 + pipeline 메타데이터 컬럼
└── summary_<ts>.txt             # 요약

data/output/dead_letter_queue.csv  # 3회 재시도 후에도 실패한 조항 (있을 경우)
```

---

## 🐳 (선택) Memgraph로 그래프 저장·시각화

저장·시각화까지 보려면 Memgraph가 필요합니다. Docker가 있다면:

```bash
docker run -p 7687:7687 -p 3000:3000 memgraph/memgraph-platform
```

`.env`에 호스트를 맞춘 뒤(`MEMGRAPH_HOST=localhost`) 실행하고, 처리 후
저장 프롬프트에서 `Y`를 선택하면 됩니다.

- **Memgraph Lab**: http://localhost:3000
- **Bolt**: bolt://localhost:7687

```cypher
// 문서 조회
MATCH (d:Document) RETURN d;

// 특정 조항과 트리플
MATCH (s:Entity)-[r:RELATION {article_number: "제1조"}]->(o:Entity)
RETURN s, r, o;

// 평가 점수가 높은 트리플 Top 10
MATCH (s:Entity)-[r:RELATION]->(o:Entity)
RETURN s.name, r.type, o.name, r.eval_score
ORDER BY r.eval_score DESC LIMIT 10;
```

---

## 🗂️ 프로젝트 구조

```
├── requirements.txt              # 로컬 CPU 최소 의존성 (OpenRouter)
├── requirements-optional.txt     # Groq/Gemini/torch/시각화 등 선택 의존성
├── .env.example                  # 환경 변수 템플릿
├── src/
│   ├── llm/
│   │   └── llm_client.py          # get_formatter/generator/evaluator_llm()
│   ├── chains/
│   │   ├── formatting_chain.py    # [A] Markdown 정규화
│   │   ├── entity_extraction_chain.py    # [C] 노드 추출
│   │   ├── relation_extraction_chain.py  # [C] 트리플 추출
│   │   └── evaluator_chain.py     # [E] 품질 평가 (LLM-as-a-Judge)
│   ├── validators/
│   │   └── rule_validator.py      # [D] 규칙 기반 검증
│   ├── graphs/
│   │   └── legal_graph.py         # LangGraph 워크플로우 + 반영 루프 + DLQ
│   ├── database/
│   │   └── memgraph_client.py     # Memgraph 저장 (+ pipeline 메타데이터)
│   ├── models/
│   │   └── schemas.py             # Pydantic 스키마 + RelationType enum
│   ├── utils/
│   │   ├── text_processor.py      # [B] split_markdown_articles 등
│   │   ├── pdf_processor.py
│   │   ├── export_utils.py        # CSV/TSV/TXT export
│   │   └── common_utils.py
│   ├── main.py                    # 샘플 텍스트 실행
│   └── process_pdf.py             # PDF 처리 실행
├── data/
│   ├── pdfs/                      # 입력 PDF
│   └── output/                    # 결과물 + DLQ
└── docs/
    └── GRAPH_QUALITY_IMPROVEMENT_PLAN.md   # 개선 계획 상세
```

---

## 🐛 트러블슈팅

**`ModuleNotFoundError: No module named 'models'`**
→ `src/` 디렉터리 **안에서** 실행했는지 확인하세요 (`cd src` 후 `python process_pdf.py`).

**OpenRouter 연결 실패**
→ `OPENROUTER_API_KEY`가 `.env`에 설정됐는지, 잔액/모델 접근 권한이 있는지 확인하세요.

**Memgraph 저장 실패 경고**
→ 정상입니다. Memgraph 없이도 결과는 `data/output/`에 저장됩니다. 저장 프롬프트에서 `N`을 선택하면 경고도 사라집니다.

**평가가 너무 느림 / 비용이 큼**
→ 전수 평가 구조입니다. `MAX_RETRIES`를 낮추거나 작은 문서로 먼저 검증하세요.

---

## 📄 라이선스

MIT License

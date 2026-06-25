# LLM-KG 그래프 품질 개선 분석 보고서 및 수정 계획

> 대상 프로젝트: `Knowledge-graph-construction-LLM-v2`
> 작성 기준: `금융회사의 지배구조에 관한 법률 시행령` 추출 결과물(nodes/triplets CSV) + Gemini 자문 대화 + 소스코드 직접 분석
> 작업 브랜치: `claude/wonderful-dirac-4cbasj` (검증 후 `main` 병합)

---

## 0. 목표 아키텍처 (핵심)

문서가 입력되면 다음 **다단계 멀티모델 파이프라인**을 거쳐 그래프 데이터를 생성한다.
이것이 프로젝트의 중심 구조이며, 과거의 단방향(정규식→생성→저장) 구조를 대체한다.

```
Document 입력
  │
  ├─ [Stage A] 초소형 LLM 전처리 (Formatter)          ★ 기본 경로
  │     원문 → Markdown 정규화(`## 제N조(제목)`), 줄바꿈 정리, 삭제조항 제거
  │     안전장치: 원문 대비 글자수 20%↓ 시 원본 fallback / 별표·서식 사전 절단
  │
  ├─ [Stage B] 단순 파싱 (Deterministic)
  │     `## ` 기준 split → 조항 청크 + structural_index(장/절 추적) 산출
  │     (Stage A 실패 시 정규식 파서로 fallback)
  │
  ├─ [Stage C] 생성 모델 (gemma4-26b-a4b 급)
  │     조항 단위로 노드(LegalEntity) + 트리플(GraphTriplet) 생성
  │
  ├─ [Stage D] 규칙 기반 1차 검증 (결정론적·무비용)
  │     스키마/enum/명사길이/포맷/자기참조/고아 검사 → 실패 시 Stage C 재호출(피드백)
  │
  ├─ [Stage E] 평가 모델 (70b 급) — LLM-as-a-Judge        ★ 실시간 품질 판단
  │     완전성(Completeness)·완결성(Faithfulness) PASS/FAIL + 실패 사유
  │
  ├─ [재생성 루프] 조항 단위. FAIL 시 사유를 피드백으로 Stage C 재생성
  │     max_retries=3, 초과 시 dead_letter_queue.csv 격리
  │
  └─ [저장] Memgraph 저장 시 pipeline_version 등 버전 속성 부착
```

**모델 역할 분리 (Model Routing)** — 모델명은 모두 설정값(env/config)으로 추상화한다.
| 역할 | 모델(기본 가정) | 비고 |
|------|----------------|------|
| 전처리 Formatter | 초소형(8B급/flash) | 빠르고 저렴, 구조 정규화 전용 |
| 생성 Generator | gemma4-26b-a4b 급 | 노드/트리플 추출 |
| 평가 Evaluator | 70b 급 | 완전성·완결성 실시간 판정 |

> 사용자 결정 사항: ① 전처리 LLM = **기본 경로**(정규식은 fallback) · ② 재생성 = **조항 단위** · ③ Memgraph 구분 = **버전 속성만**

---

## 1. 현재 산출물 품질 진단 (데이터 근거)

### 1-1. 노드(nodes CSV) 문제
| 문제 | 실제 사례 | 원인 |
|------|-----------|------|
| 파싱 아티팩트 노드 | `제124조` 행: entity_type/concept 공란, full_text=`"제124조 및"` | 본문 내 조항 인용을 독립 조항으로 오분할 |
| 과도하게 일반적인 concept | `법`, `이 영`, `자`, `회사` | 명사 강제 프롬프트의 부작용 |
| `structural_index` 미파악 | 거의 전 행이 `[]` | 장/절 구조가 파싱 단계에서 소실, LLM 추론에 위임 |
| entity_type 누락 | `제6조`, `제124조` 행 공란 | 추출 실패 시 빈값 허용 |
| full_text 과다 적재 | 금융관련법령 49개 목록이 단일 노드 | 나열형 조항을 한 덩어리로 처리 |

### 1-2. 엣지(triplets CSV) 문제
| 문제 | 실제 사례 | 원인 |
|------|-----------|------|
| object가 문장 전체 | row 18: object 60자+ 서술형 | relation 프롬프트에 명사 정제 지시 없음 |
| 스키마 외 relation | `임면한다`, `받다`, `제외한다` | `JsonOutputParser`로 enum 미강제 |
| 저신뢰도 잔존 | row 28: confidence 0.2 | 검증 단계 confidence 하한 없음 |
| 자기참조 엣지 | row 10: `은행→정의함→은행` | subject==object 필터 없음 |
| 고아(dangling) 참조 | subject/object가 노드에 부재 | 노드-엣지 교차검증 없음 |
| concepts 형식 불일치 | `"a\|b\|c"` vs 단일어 혼재 | 배열 명세 모호 |

---

## 2. 근본 원인 — 코드 레벨 (검증 완료)

- **파싱**(`text_processor.py`): 본문 내 인용구를 조항으로 오분할 / 부칙 내부 조항이 `main_raw` 오염 / 장·절 소실 / 삭제조항·별표 무방비.
- **이중 파싱**(신규 발견): `process_pdf.py:89` 구버전 `split_articles` 1차 분할 → 워크플로우가 `split_and_categorize_articles`로 2차 재분할(정규식 상이) → 버그 중복.
- **개체추출**(`entity_extraction_chain.py`): `structural_index` LLM 위임 / 실패 시 `Unknown` 더미 노드 적재(Poisoned Data).
- **관계추출**(`relation_extraction_chain.py`): `JsonOutputParser`로 enum 미강제 / object 정제 없음 / 변환 실패 시 silent `continue` / global_context 부분일치 매칭 불안정.
- **검증**(`legal_graph.py::_validate_graph`): 중복제거만 수행, confidence·자기참조·고아·enum 검증 전무.
- **저장**(`memgraph_client.py`): `:Article`(조항 메타)과 `:Entity`(트리플 양끝)가 단절되어 트리플의 출처 조항 추적 불가. 파이프라인 버전 구분 표시 없음(`model_nm`만 존재).
- **스키마 정합성**: `process_pdf.py`/`main.py`가 `LegalDocument`에 없는 `law_number` 전달.

---

## 3. Gemini 자문에 대한 객관적 평가

| 제안 | 평가 | 반영 |
|------|------|------|
| 부칙/인용 파싱 버그 수정 | 정확(데이터로 확인) | 채택 |
| 결정론적 1차 → LLM 2차 검증 이원화 | 비용/지연상 타당 | **핵심 채택** (Stage D→E) |
| Dual-Model(생성 경량 / 평가 70b) | 합리적, 인프라 의존 | **핵심 채택**, 모델명은 설정값 추상화 |
| 생성-평가-반성 루프 + Max Retries + DLQ | 품질↑, 지연/무한루프 리스크 | **핵심 채택**, 안전장치 내장(max_retries=3, DLQ) |
| LLM 전처리→Markdown→split(전략3) | 정규식 늪 회피에 효과적 | **핵심 채택(기본 경로)**, 글자수 assert·별표 절단 내장 |
| State Machine 파서(장/절 추적) | 결정론적·계층 보존 | 채택(Stage B의 structural_index 산출) |

**리스크는 "옵션화"가 아니라 "안전장치 내장"으로 통제한다**: 규칙 1차 검증으로 비싼 70b 호출을 줄이고,
max_retries+DLQ로 무한루프를 막고, 전처리 글자수 검증으로 환각·원문유실을 막고, 동의어 노드 난립은
"기존 추출어 재사용 강제 + 노드 정규화 사전"으로 전역 일관성을 지킨다.

---

## 4. 구현 로드맵 (Phased)

### Phase 0 — 인프라: 멀티모델 라우팅 + 버전 표시
- [ ] `llm_client.py`에 역할별 모델 게터 추가: `get_formatter_llm()`, `get_generator_llm()`, `get_evaluator_llm()` (env: `FORMATTER_MODEL`, `GENERATOR_MODEL`, `EVALUATOR_MODEL`).
- [ ] `GraphTriplet`/`LegalEntity` 또는 `LegalDocument`에 파이프라인 메타 추가:
      `pipeline_version`(예: `"v2-reflection"`), `generator_model`, `evaluator_model`, `eval_score`, `retry_count`.
- [ ] `memgraph_client.save_document`에서 위 속성을 `:Document`/`:Article`/`:RELATION`에 부착.
      → **별도 추출 쿼리**: `MATCH (n) WHERE n.pipeline_version='v2-reflection' RETURN n`
- [ ] export CSV/TSV에도 버전 컬럼 추가.

### Phase 1 — Stage A·B: LLM 전처리(기본) + 단순 파싱
- [ ] `src/chains/formatting_chain.py` 신설: 원문 → `## 제N조(제목)` Markdown 정규화.
      프롬프트에 "1글자도 요약·생략 금지" 명시.
- [ ] **안전장치**: 출력 글자수가 원문의 80% 미만이면 원본 사용(fallback) + 경고 로그. 단위테스트 작성.
- [ ] 별표/서식(`[별표]`, `<별지 서식>`) 전처리 전 사전 절단.
- [ ] `text_processor.split_markdown_articles()` 신설: `## ` split + 장/절 추적으로 `structural_index` 산출.
- [ ] 정규식 파서(`split_and_categorize_articles`)는 부칙 선분리 버그 수정 후 **fallback 경로**로 유지.
- [ ] `process_pdf.py` 이중 파싱 제거(워크플로우 파서로 단일화), `law_number` 정합성 수정.
- [ ] 긴 문서 대응: 물리적 블록 분할 후 전처리 → `asyncio.gather` 병렬 → 순서대로 concat.

### Phase 2 — Stage C·D: 생성 + 규칙 1차 검증
- [ ] 생성 모델을 `get_generator_llm()`로 라우팅.
- [ ] 관계추출 `JsonOutputParser → PydanticOutputParser`, relation을 `RelationType` enum으로 제약.
- [ ] relation 프롬프트에 subject/object 명사 정제 + "추출된 concept/subject/object 재사용 강제".
- [ ] `structural_index`는 파서 산출값 주입(LLM 추론 금지).
- [ ] `src/validators/rule_validator.py` 신설(결정론적): article_number 포맷 / relation·category enum / 명사 길이(≤15어절) / 자기참조 / 고아 검사.
- [ ] 개체추출 실패 시 더미 노드 대신 DLQ 격리.

### Phase 3 — Stage E + 재생성 루프 (조항 단위)
- [ ] `src/chains/evaluator_chain.py` 신설(`get_evaluator_llm()`): 원문+노드+트리플 입력 →
      완전성/완결성 PASS/FAIL + 사유 + score 반환. 기존 self-confidence 대신 evaluator score를 `confidence`로 사용.
- [ ] `legal_graph.py`에 **조항 단위 반성 루프**:
      `생성 → 규칙검증(실패 시 재생성) → 70b 평가(FAIL 시 사유 피드백 재생성)`, `max_retries=3`.
- [ ] 3회 초과 실패 조항은 `data/output/<...>/dead_letter_queue.csv`로 격리(원문+최종 사유).
- [ ] 루프 통계(조항별 retry/eval_score/PASS율) 요약 리포트 출력.

### Phase 4 — 검증·저장 강화 + 그래프 연결성
- [ ] `_validate_graph` 전역 검증: confidence 하한(기본 0.7) / 자기참조 / 고아 / enum 보정.
- [ ] (선택) `:Article`↔`:Entity` 연결 엣지 추가로 트리플 출처 조항 추적 가능화.
- [ ] 노드 정규화 사전(예: `금융위`↔`금융위원회`) 적용으로 동의어 난립 억제.

### Phase 5 — (옵션) 청킹 고도화
- [ ] `--llm-chunking`: 거대 조항(토큰 임계 초과)만 의미 분할, split index만 반환·원문 보존.

---

## 5. 변경 범위 / 리스크 / 롤백

| 파일 | 변경 | 비고 |
|------|------|------|
| `src/llm/llm_client.py` | 역할별 게터 추가 | Phase 0 |
| `src/models/schemas.py` | 파이프라인 메타 필드 | Phase 0 |
| `src/database/memgraph_client.py` | 버전 속성 부착 + (선택)연결엣지 | Phase 0/4 |
| `src/chains/formatting_chain.py` (신규) | 전처리 | Phase 1 |
| `src/utils/text_processor.py` | markdown 파서 + 정규식 버그수정 | Phase 1 |
| `src/process_pdf.py` | 이중파싱 제거 | Phase 1 |
| `src/chains/relation_extraction_chain.py` | 파서/프롬프트 | Phase 2 |
| `src/validators/rule_validator.py` (신규) | 규칙 검증 | Phase 2 |
| `src/chains/evaluator_chain.py` (신규) | 70b 평가 | Phase 3 |
| `src/graphs/legal_graph.py` | 반성 루프 + 검증강화 | Phase 3/4 |

**핵심 리스크 & 완화**
- 비용/지연 폭증 → 규칙 1차 컷오프 + 전처리/생성은 경량모델 + 평가만 70b + asyncio 병렬.
- 무한루프 → max_retries=3 + DLQ.
- 전처리 원문유실/환각 → 글자수 80% assert + fallback + 단위테스트.
- 전역 일관성 훼손 → 기존 추출어 재사용 강제 + 노드 정규화 사전.
- 재현성 저하(LLM 비결정) → temperature=0 + 정규식 fallback 보존 + 버전 속성으로 산출물 추적.

**롤백**: `pipeline_version`으로 v2 산출물을 격리 저장하므로 기존 데이터와 공존/비교 가능,
문제 시 v2 데이터만 선택 삭제(`MATCH (n {pipeline_version:'v2-reflection'}) DETACH DELETE n`).

---

## 6. 진행 원칙
1. 본 브랜치에서 Phase 단위 커밋.
2. 각 Phase마다 첨부 시행령/법률로 before/after 산출물 비교 검증.
3. 충분한 검증 후 사용자 확인 하에 `main` 병합.

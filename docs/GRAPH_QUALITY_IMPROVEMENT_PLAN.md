# LLM-KG 그래프 품질 개선 분석 보고서 및 수정 계획

> 대상 프로젝트: `Knowledge-graph-construction-LLM-v2`
> 작성 기준: `금융회사의 지배구조에 관한 법률 시행령` 추출 결과물(nodes/triplets CSV) + Gemini 자문 대화 + 소스코드 직접 분석
> 작업 브랜치: `claude/wonderful-dirac-4cbasj` (검증 후 `main` 병합)

---

## 0. 요약 (TL;DR)

현재 파이프라인은 `PDF → 정규식 청킹 → 개체추출(LLM) → 관계추출(LLM) → 중복제거 → 저장`의
단방향 구조다. 품질 저하의 근본 원인은 **(1) 파싱 단계의 구조적 결함**, **(2) 출력 스키마 강제 부재**,
**(3) 검증·재생성 루프 부재** 세 가지로 수렴한다.

Gemini 자문의 핵심 제안(생성-평가-반성 루프, Dual-Model 라우팅, 하이브리드 청킹)은 방향성이 타당하나,
**비용/지연/무한루프/전역 일관성 훼손**이라는 현실적 리스크가 있으므로 단계적·선택적으로 도입한다.
가장 비용 대비 효과가 큰 것은 **파싱 개선과 결정론적(규칙 기반) 검증**이며, LLM 평가자/반성 루프는 그 위에 얹는다.

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
| 스키마 외 relation | `임면한다`, `받다`, `제외한다`, `상위조항` | `JsonOutputParser`로 enum 미강제 |
| 저신뢰도 잔존 | row 28: confidence 0.2 (`제124조→정의함→제124조 및`) | 검증 단계 confidence 하한 없음 |
| 자기참조 엣지 | row 10: `은행→정의함→은행` | subject==object 필터 없음 |
| 고아(dangling) 참조 | subject/object가 노드에 부재 | 노드-엣지 교차검증 없음 |
| concepts 형식 불일치 | `"a\|b\|c"` vs 단일어 혼재 | 배열 명세 모호 |

---

## 2. 근본 원인 — 코드 레벨 (검증 완료)

### 2-1. 파싱 (`src/utils/text_processor.py`)
- `split_and_categorize_articles()` 정규식 `r'(제\s*\d+\s*조...|부\s*칙...)'`이
  **본문 중 인용구(예: "제124조 및")를 독립 조항으로 오분할**. (Gemini 지적 일치, 데이터로 확인)
- **부칙(addenda) 버그**: 부칙 헤더 이후 등장하는 `제1조(시행일)` 등 부칙 내부 조항이
  `main_raw`로 흡수되어 본문을 오염. `back_raw`엔 헤더만 남음. (Gemini 지적 일치)
- **장/절 계층 소실**: `structural_index`의 장/절 정보 출처가 없음.
- **삭제 조항/별표·서식 미처리**: `제N조 삭제 <날짜>`, `[별표]`, `<별지 서식>` 무방비.

### 2-2. 이중 파싱 불일치 (신규 발견 — Gemini 미지적)
- `src/process_pdf.py:89`는 **구버전** `split_articles()`로 1차 분할 후 `\n\n`로 재결합 →
  워크플로우는 다시 `split_and_categorize_articles()`로 2차 분할.
  **두 정규식이 서로 달라** 부칙/인용 버그가 두 경로에서 중복 발생.
- `process_pdf.py`/`main.py`가 스키마(`LegalDocument`)에 없는 `law_number`를 전달 → 잠재적 검증 오류.

### 2-3. 개체 추출 (`src/chains/entity_extraction_chain.py`)
- `structural_index`를 LLM에 위임 → 대부분 `[]`.
- 추출 실패 시 `LegalEntity(article_number="Unknown", ...)` **더미 노드를 그래프에 적재**(Poisoned Data). (Gemini 지적 일치)

### 2-4. 관계 추출 (`src/chains/relation_extraction_chain.py`)
- `JsonOutputParser` 사용 → `RelationType` enum 미강제 → 임의 동사 relation 양산.
- object 명사 정제 지시 없음.
- 트리플 변환 실패 시 `continue`로 **조용한 누락(Silent Failure)**. (Gemini 지적 일치)
- `global_context` 매칭이 `full_text in front_text`(부분일치) 기반이라 불안정.

### 2-5. 검증 (`src/graphs/legal_graph.py::_validate_graph`)
- (subject, relation, object) 중복 제거만 수행.
- confidence 하한 / 자기참조 / 고아 노드 / enum 위반 검증 **전무**.

---

## 3. Gemini 자문에 대한 객관적 평가

| 제안 | 평가 | 채택 여부 |
|------|------|-----------|
| 부칙/인용 파싱 버그 수정 | **정확**. 데이터로 확인됨 | ✅ 즉시 채택 (Phase 1) |
| 결정론적(규칙) 1차 검증 → LLM 2차 검증 이원화 | 비용/지연 관점에서 타당 | ✅ 채택 (Phase 2~3) |
| Dual-Model (생성=경량, 평가=70B) | 합리적이나 인프라 의존. 모델명(`gemma4-26b-a4b`)은 가용성 확인 필요 | ⚠️ 인터페이스만 추상화, 모델은 설정값으로 |
| 생성-평가-반성 루프 + Max Retries + DLQ | 품질 향상 크나 지연 2~수배. 무한루프/전역 일관성 리스크 | ⚠️ 옵션(`--reflection`)으로, max_retries=3, DLQ 도입 |
| `--llm-chunking` (하이브리드) | 거대 조항에 한해 유효. 단, 원문 유실/환각 위험 | ⚠️ 옵션화 + **글자수 assert**(20%↓ 시 fallback) 필수 |
| LLM 전처리 → Markdown → split (전략 3) | 정규식 늪 회피에 효과적이나 비결정성·비용↑ | ⚠️ 옵션(`--llm-preprocess`), 본문 한정·별표 사전 절단 |
| State Machine 파서 (장/절 추적) | 결정론적이며 계층 보존. **가장 안전한 구조 개선** | ✅ 채택 (Phase 1 핵심) |

**핵심 결론**: Gemini의 "LLM을 더 쓰자" 계열 제안(반성 루프/LLM청킹/LLM전처리)은 전부 **옵션 플래그**로
넣어 기본 경로는 빠르고 결정론적으로 유지한다. 무조건 도입 시 비용·재현성·일관성이 악화된다.

---

## 4. 수정 계획 (Phased Roadmap)

### Phase 1 — 파싱 재설계 (최우선, 결정론적)
- [ ] `text_processor.py`: 본문/부칙 **선분리** 후 본문만 조항 파싱 (부칙 버그 해소).
- [ ] 조항 앵커 정규식 강화: 줄 시작 + `제N조(제목)` 괄호 동반 조건으로 **인용 오분할 차단**.
- [ ] **State Machine 파서** 도입: 장/절을 추적해 `structural_index`/메타데이터를 코드가 직접 산출.
- [ ] 삭제 조항(`제N조 삭제 <…>`) 제거, `[별표]/<별지 서식>` 본문에서 사전 절단.
- [ ] `process_pdf.py`의 이중 파싱 제거 — 워크플로우 파서로 단일화.
- [ ] `law_number` 스키마 정합성 수정(필드 추가 또는 호출부 정리).
- [ ] **회귀 테스트**: 첨부된 시행령/법률 텍스트로 골든 파싱 결과 스냅샷 작성.

### Phase 2 — 추출 스키마 강제 (결정론적)
- [ ] 관계추출 `JsonOutputParser → PydanticOutputParser(List[GraphTriplet])` 교체, relation을 `RelationType` enum으로 제약.
- [ ] relation 프롬프트에 subject/object **명사 정제** 지시 + "추출된 concept/subject/object 재사용" 강제.
- [ ] `structural_index`는 파서 산출값을 주입(LLM 추론 금지).
- [ ] 개체추출 실패 시 더미 노드 적재 대신 **DLQ 격리**(Poisoned Data 차단).

### Phase 3 — 검증 파이프라인 강화 (`_validate_graph`)
- [ ] confidence < 임계값(기본 0.7, 설정 가능) 제거.
- [ ] subject==object 자기참조 제거.
- [ ] 노드맵 기반 **고아 엣지 제거/보정**.
- [ ] relation enum 위반 시 nearest-match 보정 또는 제거.
- [ ] 검증 리포트(제거 사유별 카운트) 출력.

### Phase 4 — (옵션) LLM 평가자 / 반성 루프
- [ ] `src/chains/evaluator_chain.py` 신설(70B급, 모델은 설정값). PASS/FAIL + 사유 반환.
- [ ] 워크플로우에 `--reflection` 플래그: 규칙검증→LLM평가→실패 시 피드백 재생성(max_retries=3).
- [ ] 3회 초과 실패분 `dead_letter_queue.csv` 격리.

### Phase 5 — (옵션) 청킹/전처리 고도화
- [ ] `--llm-chunking`: 거대 조항(토큰 임계 초과)만 의미 분할, split index만 반환·원문 보존.
- [ ] `--llm-preprocess`: 경량 모델로 Markdown 정규화 후 `## 제N조` split. **글자수 20%↓ 시 원본 fallback** 단위테스트.

---

## 5. 변경 범위 / 리스크

| 파일 | 변경 수준 | 회귀 위험 |
|------|-----------|-----------|
| `src/utils/text_processor.py` | 대 | 중 (골든 테스트로 방어) |
| `src/process_pdf.py` | 중 (이중 파싱 제거) | 중 |
| `src/chains/relation_extraction_chain.py` | 중 (파서/프롬프트) | 중 |
| `src/graphs/legal_graph.py` | 중 (검증 강화 + 옵션 분기) | 중 |
| `src/chains/entity_extraction_chain.py` | 소 (DLQ, 필드 강제) | 저 |
| `src/models/schemas.py` | 소 | 저 |
| `src/chains/evaluator_chain.py` (신규) | — | 저 (옵션) |

**롤백 전략**: 모든 LLM 추가 사용은 플래그 뒤에 격리. 기본 경로는 Phase 1~3만 거치므로
기존 동작 대비 결정론적이며, 문제가 생기면 플래그만 비활성화.

---

## 6. 진행 원칙
1. 본 브랜치(`claude/wonderful-dirac-4cbasj`)에서 Phase 단위 커밋.
2. 각 Phase마다 첨부 시행령/법률로 before/after 산출물 비교 검증.
3. 충분한 검증 후 사용자 확인 하에 `main` 병합.

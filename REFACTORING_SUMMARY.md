# 코드 통합 및 리팩토링 요약

## 개요
이 문서는 `process_pdf.py`와 `main.py` 간의 중복 코드를 제거하고 코드를 통합한 작업을 설명합니다.

## 수행한 작업

### 1. 공통 유틸리티 모듈 생성 (`src/utils/common_utils.py`)

다음 중복 함수들을 공통 모듈로 이동했습니다:

#### a. `check_gpu()` 함수
- GPU 가용성 및 CUDA 버전을 확인하는 함수
- 두 스크립트에서 동일하게 사용되던 코드를 하나로 통합

#### b. `test_llm_connection()` 함수
- LLM 연결 상태를 테스트하는 함수
- Gemini API 또는 로컬 LLM 연결 확인
- 에러 발생 시 상세한 가이드 제공

#### c. `save_to_memgraph()` 함수
- 처리된 문서를 Memgraph 데이터베이스에 저장
- `clear_existing` 매개변수로 기존 데이터 삭제 여부 제어
- 두 스크립트에서 사용되던 저장 로직을 통합

#### d. `display_result_tables()` 함수
- 추출된 개체와 관계를 Rich 테이블로 표시
- 두 스크립트에서 반복되던 테이블 생성 코드 통합
- `max_items` 매개변수로 출력 항목 수 제어

### 2. `process_pdf.py` 업데이트

#### 변경 사항:
- `utils.text_processor`의 `clean_text()` 함수를 사용하여 PDF에서 추출한 텍스트 정제
- `utils.text_processor`의 `split_articles()` 함수를 사용하여 PDF 텍스트를 조항별로 파싱
- 공통 유틸리티 함수 사용 (`check_gpu`, `test_llm_connection`, `save_to_memgraph`, `display_result_tables`)
- 중복 코드 제거 (약 80줄 감소)
- Memgraph 저장 시 사용자에게 기존 데이터 삭제 여부 확인

#### 주요 개선점:
```python
# 이전
content = extract_text_from_pdf(pdf_path)

# 이후 (텍스트 정제 및 조항 파싱 추가)
content = extract_text_from_pdf(pdf_path)
content = clean_text(content)

# split_articles를 사용하여 조항별로 분리하고 다시 결합
articles = split_articles(content)
content = "\n\n".join(articles)
```

### 3. `main.py` 업데이트

#### 변경 사항:
- 공통 유틸리티 함수 사용
- 중복 코드 제거 (약 70줄 감소)
- Memgraph 저장 시 자동으로 기존 데이터 삭제 (`clear_existing=True`)

#### 간소화된 코드:
```python
# 이전: 긴 테이블 생성 코드 (약 40줄)
entity_table = Table(...)
for entity in result.entities[:10]:
    entity_table.add_row(...)
console.print(entity_table)
# ... 관계 테이블도 동일

# 이후: 간단한 함수 호출
display_result_tables(result)
```

### 4. 의존성 관리 개선

#### `src/utils/__init__.py`:
- 순환 임포트 방지를 위해 지연 로딩 방식 사용
- 필요한 함수만 직접 임포트하도록 개선

#### `src/utils/common_utils.py`:
- `MemgraphClient` 임포트를 함수 내부로 이동하여 의존성 문제 해결
- 모듈 임포트 시 gqlalchemy 등의 의존성이 필수가 아니도록 개선

## 결과

### 코드 감소량
- `process_pdf.py`: 약 80줄 감소 (267줄 → 187줄)
- `main.py`: 약 70줄 감소 (156줄 → 86줄)
- 새로 생성: `common_utils.py` (145줄)
- **순 감소량: 약 5줄 + 중복 제거로 인한 유지보수성 향상**

### 개선점

1. **코드 재사용성**: 공통 로직이 하나의 모듈에 집중됨
2. **유지보수성**: 버그 수정이나 기능 개선 시 한 곳만 수정하면 됨
3. **일관성**: 두 스크립트가 동일한 동작을 보장
4. **테스트 가능성**: 공통 함수를 독립적으로 테스트 가능
5. **의존성 관리**: 지연 로딩으로 불필요한 의존성 제거

## 테스트 결과

기존 테스트를 실행하여 변경 사항이 기존 기능을 손상시키지 않았음을 확인:

```bash
pytest tests/test_pdf_processor.py tests/test_text_processor.py -v
```

**결과**: 모든 테스트 통과 (13/13) ✅

## 사용 방법

### process_pdf.py 실행
```bash
cd src
python process_pdf.py
```

PDF 파일을 선택하고 지식 그래프를 생성합니다.

### main.py 실행
```bash
cd src
python main.py
```

샘플 법률 문서로 지식 그래프를 생성합니다.

## 향후 개선 사항

1. 추가적인 유틸리티 함수 통합 가능성 검토
2. 설정 파일을 통한 매개변수 관리
3. 로깅 시스템 추가
4. 에러 핸들링 강화

## 참고

- `utils.text_processor`의 `clean_text()` 함수는 연속된 공백 제거 및 특수문자 정규화를 수행합니다.
- `utils.text_processor`의 `split_articles()` 함수는 법령 텍스트를 조항별로 분리합니다. PDF에서 추출한 텍스트를 조항 단위로 구조화하여 더 정확한 파싱이 가능합니다.
- PDF 처리 시 텍스트는 먼저 정제(`clean_text`)되고, 조항으로 분리(`split_articles`)된 후, 다시 결합되어 워크플로우에 전달됩니다.

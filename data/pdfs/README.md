# PDF 파일 저장 디렉토리

이 디렉토리에 처리하고자 하는 법률 문서 PDF 파일을 저장하세요.

## 사용 방법

1. **PDF 파일 추가**
   ```bash
   # 이 디렉토리에 PDF 파일을 복사
   cp /path/to/your/법률문서.pdf ./
   ```

2. **PDF 처리 실행**
   ```bash
   # 프로젝트 루트 디렉토리에서 실행
   cd /home/runner/work/Knowledge-graph-construction-LLM-v2/Knowledge-graph-construction-LLM-v2
   python src/process_pdf.py
   ```

3. **처리 과정**
   - 스크립트가 이 디렉토리의 PDF 파일 목록을 표시합니다
   - 처리할 파일 번호를 선택합니다
   - 자동으로 텍스트를 추출하고 지식 그래프를 생성합니다

## 지원되는 파일 형식

- PDF 파일 (`.pdf`)
- 텍스트가 포함된 PDF (스캔 이미지 PDF는 지원하지 않음)

## 예제

```
data/pdfs/
├── 개인정보보호법.pdf
├── 저작권법.pdf
└── 특허법.pdf
```

## 주의사항

- PDF 파일명은 한글을 포함할 수 있습니다
- 파일 크기가 너무 크면 처리 시간이 오래 걸릴 수 있습니다
- 스캔된 이미지 PDF는 OCR 처리가 필요합니다 (현재 미지원)

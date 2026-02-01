#!/bin/bash
# .env 파일을 로드하고 process_pdf.py를 실행하는 래퍼 스크립트

# .env 파일 로드
if [ -f "/app/.env" ]; then
    export $(grep -v '^#' /app/.env | xargs)
    echo "✅ .env 파일 로드 완료"
fi

# process_pdf.py 실행
cd /app/src
poetry run python process_pdf.py "$@"

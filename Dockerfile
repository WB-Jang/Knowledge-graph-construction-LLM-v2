# 1. 베이스 이미지: GPU 컴파일이 가능한 devel 사용
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

# 2. 환경 변수 설정
ENV POETRY_HOME="/home/appuser/. local" \
    PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    DEBIAN_FRONTEND=noninteractive \
    CUDA_HOME=/usr/local/cuda \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}

# 3. 시스템 패키지 설치 (Root)
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \ 
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    curl \
    build-essential \
    cmake \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3.11 /usr/bin/python \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# 4. 사용자 생성 및 설정
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app && \
    chown -R appuser: appuser /app

WORKDIR /app
USER appuser

# 5. Poetry 설치
RUN curl -sSL https://install.python-poetry.org | python3 -

# 6. 의존성 파일 복사 (레이어 캐싱 최적화)
COPY --chown=appuser:appuser pyproject.toml poetry.lock* ./

# 7. 의존성 설치 + GPU llama-cpp-python 빌드
RUN poetry install --no-root --no-interaction && \
    CMAKE_ARGS="-DGGML_CUDA=on" poetry run pip install llama-cpp-python \
    --upgrade --force-reinstall --no-cache-dir --verbose

# 8. GPU 확인 스크립트 추가
USER root
RUN echo '#!/bin/bash\n\
echo "🔍 GPU 정보: "\n\
nvidia-smi 2>/dev/null || echo "⚠️ GPU를 찾을 수 없습니다"\n\
python -c "import torch; print(f\"PyTorch CUDA:  {torch.cuda.is_available()}\")" 2>/dev/null || echo "PyTorch 미설치"\n\
python -c "from llama_cpp import Llama; print(\"✅ llama-cpp-python GPU 빌드 성공\")" 2>/dev/null || echo "❌ llama-cpp-python GPU 빌드 실패"\n\
' > /usr/local/bin/check-gpu && chmod +x /usr/local/bin/check-gpu

USER appuser

# 9. 소스 코드 복사
COPY --chown=appuser:appuser . .

# 10. 실행 명령어
# CMD ["poetry", "run", "python", "src/main.py"]

FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    git \
    curl \
    build-essential \
    wget \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Python 기본 버전 설정
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Poetry 설치
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# 작업 디렉토리 설정
WORKDIR /workspace

# Poetry 설정
RUN poetry config virtualenvs.in-project true

# 의존성 파일 복사
COPY pyproject.toml poetry.lock* ./

# 의존성 설치 (개발 의존성 포함)
RUN poetry install --no-root --with dev

# 소스 코드 복사
COPY .  .

# 프로젝트 설치
RUN poetry install

# GPU 확인 스크립트
RUN echo '#!/bin/bash\n\
echo "🔍 GPU 정보: "\n\
nvidia-smi 2>/dev/null || echo "⚠️ GPU를 찾을 수 없습니다"\n\
python -c "import torch; print(f\"PyTorch CUDA 사용 가능: {torch.cuda.is_available()}\")" 2>/dev/null || echo "PyTorch 미설치"\n\
' > /usr/local/bin/check-gpu && chmod +x /usr/local/bin/check-gpu

# 기본 명령어
CMD ["poetry", "run", "python", "src/main.py"]

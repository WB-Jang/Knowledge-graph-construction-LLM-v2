# 개발 시에는 아래의 코드를 사용하고, 

# 1. 베이스 이미지
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

# 2. 환경 변수
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    CUDA_HOME=/usr/local/cuda \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}

# 3. 시스템 패키지
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

# 4. 사용자 생성 - UID/GID를 동적으로 설정
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid $USER_GID appuser && \
    useradd --uid $USER_UID --gid $USER_GID --create-home --shell /bin/bash appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

# 5. Poetry 환경 변수
ENV POETRY_HOME="/home/appuser/.local" \
    PATH="/home/appuser/.local/bin:$PATH" \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app
USER appuser

# 6. Poetry 설치
RUN python3 -m pip install --user poetry && \
    poetry --version

# 7. 의존성 파일만 복사 (소스 코드는 볼륨 마운트로 제공)
COPY --chown=appuser:appuser pyproject.toml poetry.lock* ./

# 8. 리눅스 환경에 맞게 락 파일 초기화
RUN rm -f poetry.lock

# 9. Poetry 의존성 설치
RUN poetry install --no-root --no-interaction || \
    (echo "❌ Poetry 설치 실패" && exit 1)

# ❌ 소스 코드 복사 제거 - 볼륨 마운트로 대체
# COPY --chown=appuser:appuser . .

# 10. 실행 명령어
CMD ["/bin/bash"]

# 배포시에는 아래의 코드를 사용할 것

# # 1. 베이스 이미지
# FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

# # 2. 환경 변수
# ENV PYTHONUNBUFFERED=1 \
#     DEBIAN_FRONTEND=noninteractive \
#     CUDA_HOME=/usr/local/cuda \
#     LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}

# # 3. 시스템 패키지
# USER root
# RUN apt-get update && apt-get install -y --no-install-recommends \ 
#     python3.11 \
#     python3.11-venv \
#     python3.11-dev \
#     python3-pip \
#     curl \
#     build-essential \
#     cmake \
#     git \
#     wget \
#     && rm -rf /var/lib/apt/lists/* \
#     && ln -s /usr/bin/python3.11 /usr/bin/python \
#     && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# # 4. 사용자 생성
# RUN useradd --create-home --shell /bin/bash appuser && \
#     mkdir -p /app && \
#     chown -R appuser:appuser /app

# # 5. Poetry 환경 변수
# ENV POETRY_HOME="/home/appuser/.local" \
#     PATH="/home/appuser/.local/bin:$PATH" \
#     POETRY_VIRTUALENVS_CREATE=true \
#     POETRY_VIRTUALENVS_IN_PROJECT=true

# WORKDIR /app
# USER appuser

# # 6. Poetry 설치
# RUN python3 -m pip install --user poetry && \
#     poetry --version

# # 7. 의존성 파일 복사 (중요:  빌드 시점에 복사)
# COPY --chown=appuser:appuser pyproject.toml poetry.lock* ./

# # [추가] 리눅스 환경에 맞게 락 파일 초기화 (기존 락 파일 삭제)
# RUN rm -f poetry.lock

# # 8. Poetry 의존성 설치 (llama-cpp-python 제외)
# RUN poetry install --no-root --no-interaction || \
#     (echo "❌ Poetry 설치 실패" && exit 1)

# # 9. 소스 코드 복사
# COPY --chown=appuser:appuser .  . 

# # 10. 실행 명령어
# CMD ["/bin/bash"]
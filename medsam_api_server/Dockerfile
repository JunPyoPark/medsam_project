FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_ROOT=/app/data \
    CELERY_BROKER_URL=redis://redis:6379/0 \
    CELERY_RESULT_BACKEND=redis://redis:6379/1 \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONPATH=/app \
    CUDA_HOME=/usr/local/cuda \
    TORCH_CUDA_ARCH_LIST="6.0;6.1;7.0;7.5;8.0;8.6;9.0"

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    git \
    wget \
    curl \
    build-essential \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Python 기본 설정
RUN ln -s /usr/bin/python3.10 /usr/bin/python
RUN python -m pip install --upgrade pip

WORKDIR /app

# PyTorch GPU 버전 설치 (CUDA 12.1)
RUN pip install torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121

# MedSAM2 의존성 설치
COPY medsam_api_server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# MedSAM2 소스 복사 (빌드 시점에)
COPY MedSAM2 /app/MedSAM2

# MedSAM2 설치 (빌드 시점에)
WORKDIR /app/MedSAM2
RUN pip install numpy setuptools wheel --quiet && \
    pip install -e . --quiet || \
    (echo "⚠️ CUDA extensions failed, trying without..." && \
     FORCE_CUDA=0 pip install -e . --quiet)

# API 서버 코드 복사
WORKDIR /app
COPY medsam_api_server /app/medsam_api_server

# 데이터 및 모델 디렉토리 생성
RUN mkdir -p /app/data /app/models /app/temp

# 모델 다운로드 스크립트 (나중에 실행)
COPY scripts/download_models.sh /app/scripts/
RUN chmod +x /app/scripts/download_models.sh

EXPOSE 8000

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 시작 스크립트 생성
RUN cat > /app/start_server.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Starting MedSAM2 GPU Service..."
echo "Working directory: $(pwd)"
echo "Python path: $PYTHONPATH"
echo "CUDA_HOME: $CUDA_HOME"

# MedSAM2는 빌드 시점에 이미 설치됨
echo "📦 MedSAM2 already installed during build"

# Python 모듈 확인
echo "🔍 Checking Python modules..."
python -c "import medsam_api_server; print('✅ medsam_api_server module found')" || echo "❌ medsam_api_server module not found"

# sam2 모듈 확인
python -c "import sam2; print('✅ sam2 module found')" 2>/dev/null || echo "⚠️ sam2 module not available - API will run in limited mode"

echo "🌐 Starting API server..."
cd /app
uvicorn medsam_api_server.main:app --host 0.0.0.0 --port 8000
EOF

RUN chmod +x /app/start_server.sh

CMD ["/app/start_server.sh"]

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
uvicorn medsam_api_server.main:app --host 0.0.0.0 --port 8000 --workers 4 --log-config /app/medsam_api_server/logging.conf


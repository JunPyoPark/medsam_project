#!/bin/bash

# MedSAM2 모델 다운로드 스크립트
set -e

# 스크립트 위치 기준으로 프로젝트 루트 자동 탐지
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODEL_DIR="$PROJECT_ROOT/models"

mkdir -p "$MODEL_DIR"

echo "📦 MedSAM2 모델 다운로드 중..."
echo "모델 디렉토리: $MODEL_DIR"

# MedSAM2 체크포인트 다운로드
if [ ! -f "$MODEL_DIR/MedSAM2_latest.pt" ] || [ ! -s "$MODEL_DIR/MedSAM2_latest.pt" ]; then
    echo "🔽 MedSAM2 체크포인트 다운로드 중... (약 149MB)"
    wget -O "$MODEL_DIR/MedSAM2_latest.pt" \
        "https://huggingface.co/wanglab/MedSAM2/resolve/main/MedSAM2_latest.pt" || {
        echo "❌ 다운로드 실패. 수동으로 다운로드하세요:"
        echo "   wget https://huggingface.co/wanglab/MedSAM2/resolve/main/MedSAM2_latest.pt -O $MODEL_DIR/MedSAM2_latest.pt"
        exit 1
    }
    echo "✅ MedSAM2 체크포인트 다운로드 완료"
else
    echo "✅ MedSAM2 체크포인트 이미 존재함"
fi

# SAM2 configuration (이미 포함되어 있음)
if [ ! -f "$MODEL_DIR/sam2.1_hiera_t512.yaml" ]; then
    echo "⚠️  SAM2 설정 파일이 없습니다. 프로젝트에 포함되어 있어야 합니다."
else
    echo "✅ SAM2 설정 파일 확인됨"
fi

echo ""
echo "🎉 모델 다운로드 완료!"
echo ""
ls -lh "$MODEL_DIR" 
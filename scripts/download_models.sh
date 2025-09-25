#!/bin/bash

# MedSAM2 모델 다운로드 스크립트
set -e

MODEL_DIR="/app/models"
mkdir -p $MODEL_DIR

echo "Downloading MedSAM2 models..."

# MedSAM2 체크포인트 다운로드
if [ ! -f "$MODEL_DIR/MedSAM2_latest.pt" ]; then
    echo "Downloading MedSAM2 checkpoint..."
    wget -O "$MODEL_DIR/MedSAM2_latest.pt" \
        "https://github.com/MedSAM2/MedSAM2/releases/download/v1.0.0/MedSAM2_latest.pt" || \
    echo "Warning: Could not download MedSAM2 checkpoint. Please download manually."
fi

# SAM2 configuration
if [ ! -f "$MODEL_DIR/sam2.1_hiera_t512.yaml" ]; then
    echo "Downloading SAM2 config..."
    wget -O "$MODEL_DIR/sam2.1_hiera_t512.yaml" \
        "https://raw.githubusercontent.com/MedSAM2/MedSAM2/main/configs/sam2.1_hiera_t512.yaml" || \
    echo "Warning: Could not download SAM2 config. Please download manually."
fi

echo "Model download complete!"
ls -la $MODEL_DIR 
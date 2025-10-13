# Models Directory

## Required Files

This directory should contain:
- `MedSAM2_latest.pt` - MedSAM2 checkpoint (148MB)
- `sam2.1_hiera_t512.yaml` - SAM2 configuration

## Download

These files are not included in the repository due to size limitations.

### Option 1: Automatic Download (권장)
```bash
# 프로젝트 어디서든 실행 가능
chmod +x scripts/download_models.sh
./scripts/download_models.sh
```

### Option 2: Manual Download
```bash
cd models
wget https://huggingface.co/wanglab/MedSAM2/resolve/main/MedSAM2_latest.pt -O MedSAM2_latest.pt
```

**다운로드 확인:**
```bash
ls -lh models/MedSAM2_latest.pt
# 예상 크기: 약 149MB
```

## Note
- The `.pt` files are excluded from Git via `.gitignore`
- Total size: ~150MB

# Models Directory

## Required Files

This directory should contain:
- `MedSAM2_latest.pt` - MedSAM2 checkpoint (148MB)
- `sam2.1_hiera_t512.yaml` - SAM2 configuration

## Download

These files are not included in the repository due to size limitations.

### Option 1: Automatic Download
```bash
cd /path/to/medsam_project
chmod +x scripts/download_models.sh
./scripts/download_models.sh
```

### Option 2: Manual Download
1. Visit [MedSAM2 Official Repository](https://github.com/bowang-lab/MedSAM2)
2. Download the model files from Releases or Hugging Face
3. Place them in this directory

### Hugging Face (Alternative)
```bash
cd models
wget https://huggingface.co/wanglab/MedSAM2/resolve/main/medsam2_hiera_l.pt -O MedSAM2_latest.pt
```

## Note
- The `.pt` files are excluded from Git via `.gitignore`
- Total size: ~150MB

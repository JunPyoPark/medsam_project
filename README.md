# MedSAM2 HITL: 3D 의료영상 분할 시스템

**MedSAM2** 모델을 활용한 **Human-in-the-Loop (HITL)** 3D 의료영상 분할 웹 애플리케이션입니다. 
의료 전문가가 AI와 협력하여 3D 의료 영상(CT, MRI 등)에서 병변이나 장기를 효율적으로 분할할 수 있도록 지원합니다.

---

## 📋 목차

- [핵심 기능](#-핵심-기능)
- [핵심 개념](#-핵심-개념)
- [시스템 아키텍처](#️-시스템-아키텍처)
- [빠른 시작](#-빠른-시작)
- [설치 및 설정](#️-설치-및-설정)
  - [방법 1: Docker 사용](#방법-1-docker-사용-권장)
  - [방법 2: 로컬 설치](#방법-2-로컬-설치-docker-없이)
- [설치 확인](#-설치-확인)
- [사용법](#-사용법)
- [프로젝트 구조](#-프로젝트-구조)
- [API 엔드포인트](#-api-엔드포인트)
- [개발 가이드](#-개발-가이드)
- [문제 해결](#-문제-해결)
- [주요 기술 스택](#-주요-기술-스택)
- [주의사항](#-주의사항)
- [사용 팁](#-사용-팁)
- [지원 및 기여](#-지원-및-기여)
- [참고 자료](#-참고-자료)
- [라이선스](#-라이선스)

---

## 🎯 핵심 기능

### 1. 3D 의료영상 뷰어
- **입력**: NIfTI (.nii.gz) 파일
- **표시**: 2D 슬라이스 뷰어 (90도 회전하여 정방향 표시)
- **조작**: 슬라이더로 슬라이스 이동, 좌표 입력으로 분할 영역 지정

### 2. 2D 분할 (중간 슬라이스)
- **사용자 입력**: x1, y1, x2, y2 좌표로 사각형 영역 지정
- **AI 처리**: MedSAM2 모델로 2D 분할 수행
- **결과**: 빨간색 마스크로 분할 영역 표시

### 3. 3D Propagation
- **입력**: 2D 분할 결과를 기반으로
- **처리**: 중간 슬라이스에서 양방향으로 3D 전파
- **결과**: 전체 3D 마스크 생성 및 다운로드

---

## ✨ 핵심 개념

### 1. MedSAM2 (Segment Anything in 3D Medical Images)
MedSAM2는 2D 및 3D 의료 영상을 분할하기 위한 최첨단 파운데이션 모델입니다. 점, 경계 상자, 텍스트 등 다양한 프롬프트를 기반으로 정확한 분할 마스크를 생성할 수 있습니다.
- **공식 저장소**: [MedSAM2 GitHub](https://github.com/bowang-lab/MedSAM2)

### 2. Human-in-the-Loop (HITL)
사람(전문가)과 AI가 협력하여 작업을 수행하는 방식입니다. AI의 속도와 사람의 전문성을 결합하여 라벨링 시간을 획기적으로 단축하고 정확도를 높입니다.

**HITL 선순환 구조:**
1. **사람의 개입**: 전문의가 3D 영상의 특정 2D 슬라이스에 간단한 경계 상자를 그립니다.
2. **AI의 자동화**: MedSAM2가 경계 상자를 기반으로 2D 마스크를 생성하고, 이를 3D 전체로 전파하여 3D 마스크 초안을 만듭니다.
3. **사람의 검토**: 전문의가 AI가 생성한 3D 마스크를 검토하고 필요시 수정합니다.
4. **(향후) AI 재학습**: 정제된 고품질 데이터는 AI 모델을 재학습시켜 성능을 점진적으로 향상시킵니다.

### 3. 비동기 API 아키텍처
3D 의료 영상 분할은 수십 초에서 수 분까지 소요될 수 있는 무거운 작업입니다. 비동기 아키텍처는 이러한 작업이 UI를 차단하지 않도록 보장합니다.

- **FastAPI (API 서버)**: 클라이언트의 요청을 즉시 수신하고, 무거운 작업은 Celery 작업 큐에 전달
- **Celery & Redis (작업 큐)**: 전달받은 작업을 백그라운드에서 순차적으로 처리
- **Celery Worker (GPU 워커)**: 실제 MedSAM2 모델을 실행하여 분할 작업 수행
- **클라이언트 (Gradio)**: 작업 ID를 받아 주기적으로 서버에 진행 상태를 폴링하고, 완료 시 결과 표시

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    HTTP API    ┌─────────────────┐
│   Gradio UI     │◄──────────────►│   FastAPI       │
│   (Frontend)    │                │   (Backend)     │
└─────────────────┘                └─────────────────┘
                                           │
                                           ▼
                                   ┌─────────────────┐
                                   │   Celery Queue  │
                                   │   (Redis)       │
                                   └─────────────────┘
                                           │
                                           ▼
                                   ┌─────────────────┐
                                   │   Celery Worker │
                                   │  (AI Processing)│
                                   └─────────────────┘
```

### 컴포넌트 설명

#### 프론트엔드 (Gradio)
- **파일**: `medsam_gradio_viewer/app.py`
- **역할**: 사용자 인터페이스, 이미지 표시, 사용자 입력 처리
- **기술**: Gradio 4.44.1, NumPy, Nibabel

#### 백엔드 (FastAPI)
- **파일**: `medsam_api_server/main.py`, `medsam_api_server/api/v1/jobs.py`
- **역할**: API 서버, 파일 업로드, 작업 관리
- **기술**: FastAPI, Uvicorn

#### 작업 큐 (Celery + Redis)
- **파일**: `medsam_api_server/celery_app.py`, `medsam_api_server/tasks/segmentation.py`
- **역할**: 비동기 AI 작업 처리
- **기술**: Celery, Redis

#### GPU 관리 및 모델 로딩
- **파일**: `medsam_api_server/core/gpu_manager.py`, `medsam_api_server/core/model_manager.py`
- **역할**: GPU 메모리 관리, MedSAM2 모델 로딩 및 추론
- **기술**: PyTorch, CUDA

---

## 🚀 빠른 시작

### 📋 사전 요구사항

**필수:**
- Python 3.10+ (권장: Python 3.12)
- Redis 서버
- 가상환경 (권장)

**선택 (AI 처리 가속화):**
- NVIDIA GPU (CUDA 지원)
- NVIDIA 드라이버
- CUDA Toolkit
- NVIDIA Container Toolkit (Docker 사용 시)

### 설치 방법 선택
- **방법 1: Docker 사용** - 권장, 환경 설정이 간단함
- **방법 2: 로컬 설치** - Docker 없이 직접 설치

> 자세한 설치 방법은 아래 [설치 및 설정](#️-설치-및-설정) 섹션을 참고하세요.

### 1. 초기 설정 (최초 1회만) - 간략 버전

**Docker 방식 (프로덕션):**
```bash
# 1. 시스템 준비 (Docker, NVIDIA 드라이버 등)
# 2. 프로젝트 클론
git clone https://github.com/junpyopark/medsam_project.git
cd medsam_project

# 3. MedSAM2 클론 (빌드에 필요)
git clone https://github.com/bowang-lab/MedSAM2.git

# 4. 디렉토리 생성
mkdir -p data temp models

# 5. Docker Compose 빌드 및 실행
docker compose up --build -d

# 6. Gradio 실행 (별도 터미널)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r medsam_gradio_viewer/requirements.txt
python medsam_gradio_viewer/app.py
```

> **참고**: 프로덕션 모드에서 MedSAM2는 빌드 시점에 이미지에 포함되므로, 
> 빌드 후에는 로컬의 MedSAM2 폴더를 삭제해도 됩니다.

**로컬 방식:**
```bash
# 1. 시스템 준비 (Python, Redis, NVIDIA 드라이버 등)
# 2. 프로젝트 클론
git clone https://github.com/junpyopark/medsam_project.git
cd medsam_project
git clone https://github.com/bowang-lab/MedSAM2.git

# 3. 가상환경 및 설치
python3.12 -m venv .venv
source .venv/bin/activate
mkdir -p data temp models
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r medsam_api_server/requirements.txt
pip install -r medsam_gradio_viewer/requirements.txt
cd MedSAM2 && pip install -e . && cd ..

# 4. 서비스 시작
./scripts/start.sh
```

### 2. 서비스 시작 (이미 설치된 경우)
```bash
cd /path/to/medsam_project

# 가상환경 활성화 (필요시)
source .venv/bin/activate

# 모든 서비스 시작 (Redis, FastAPI, Celery, Gradio)
./scripts/start.sh
```

### ✅ 새 서버 빠른 실행 스크립트 활용

> Docker 환경에서 Gradio까지 한 번에 기동하고 싶을 때 사용하세요.

```bash
cd /path/to/medsam_project

# (최초 1회) 시스템 의존성 점검
./scripts/check_prerequisites.sh

# (최초 1회) Gradio용 가상환경 생성
# python3.12이 없다면 apt로 python3.12-venv 설치 후 실행
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r medsam_gradio_viewer/requirements.txt

# (매 실행 시) 빠른 시작
./scripts/quick_start.sh
```

> `python3.12 -m venv` 실행 시 `ensurepip` 오류가 발생하면 `sudo apt install python3.12-venv` 를 설치한 뒤 다시 시도하세요.

### 3. 웹 접속
- **Gradio UI** (사용자 인터페이스): http://127.0.0.1:7860
- **API 서버** (루트): http://127.0.0.1:8000
- **API 문서** (Swagger UI): http://127.0.0.1:8000/docs
- **API 문서** (ReDoc): http://127.0.0.1:8000/redoc
- **Health Check**: http://127.0.0.1:8000/health
- **Celery 모니터** (Flower): http://127.0.0.1:5556

### 4. 기본 사용 흐름

#### Step 1: NIfTI 파일 업로드
1. 브라우저에서 http://127.0.0.1:7860 접속
2. "NIfTI (.nii.gz) 업로드"에서 파일 선택
3. "새 작업 시작" 버튼 클릭

#### Step 2: 2D 분할
1. 슬라이더로 원하는 슬라이스로 이동
2. x1, y1, x2, y2 좌표 입력 (예: 200, 265, 240, 310)
3. "현재 슬라이스 2D 분할" 버튼 클릭
4. 자동으로 완료까지 대기 (빨간색 마스크 표시)

#### Step 3: 3D Propagation
1. "3D Propagation 실행" 버튼 클릭
2. 진행률 바로 처리 상황 확인
3. 완료 시 다운로드 링크 활성화
4. 3D 마스크 다운로드 (.nii.gz)

---

## 🛠️ 설치 및 설정

### 📋 새 서버 완전 설치 체크리스트

**새 서버에 처음 설치하는 경우, 이 체크리스트를 따라 진행하세요:**

#### 설치 전 준비
- [ ] Ubuntu 20.04/22.04 서버 준비
- [ ] sudo 권한 확보
- [ ] 인터넷 연결 확인
- [ ] 디스크 공간 20GB 이상 확보

#### 시스템 설정 (Docker 방식)
- [ ] 시스템 업데이트: `sudo apt-get update && sudo apt-get upgrade -y`
- [ ] Docker 설치: `curl -fsSL https://get.docker.com | sudo sh`
- [ ] Docker 그룹 추가: `sudo usermod -aG docker $USER`
- [ ] 로그아웃 후 재로그인 (또는 `newgrp docker`)
- [ ] Docker 버전 확인: `docker --version`
- [ ] GPU 사용 시: NVIDIA 드라이버 설치 후 재부팅
- [ ] GPU 사용 시: nvidia-container-toolkit 설치

#### 프로젝트 설정
- [ ] 프로젝트 클론: `git clone https://github.com/junpyopark/medsam_project.git`
- [ ] 프로젝트 폴더 이동: `cd medsam_project`
- [ ] **⚠️ 중요**: MedSAM2 클론: `git clone https://github.com/bowang-lab/MedSAM2.git`
- [ ] MedSAM2 확인: `ls MedSAM2/setup.py` (파일이 있어야 함)
- [ ] 디렉토리 생성: `mkdir -p data temp models`
- [ ] 모델 다운로드 (선택): `chmod +x scripts/download_models.sh && ./scripts/download_models.sh`

#### Docker 빌드 및 실행
- [ ] 빌드 시작: `docker compose up --build -d` (10-20분 소요)
- [ ] 별도 터미널에서 빌드 로그 확인: `docker compose logs -f api`
- [ ] 빌드 완료 대기 (에러 없이 완료되어야 함)
- [ ] 컨테이너 상태 확인: `docker compose ps` (모두 "Up" 상태)

#### Gradio 프론트엔드 실행
- [ ] 새 터미널 열기
- [ ] 가상환경 생성: `python3.12 -m venv .venv`
- [ ] 가상환경 활성화: `source .venv/bin/activate`
- [ ] 의존성 설치: `pip install -r medsam_gradio_viewer/requirements.txt`
- [ ] Gradio 실행: `python medsam_gradio_viewer/app.py`

#### 설치 확인
- [ ] API 서버: `curl http://localhost:8000/health`
- [ ] Redis: `docker compose exec api redis-cli -h redis ping`
- [ ] GPU (GPU 사용 시): `docker compose exec worker nvidia-smi`
- [ ] MedSAM2 모듈: `docker compose exec worker python -c "import sam2"`
- [ ] Gradio UI: 브라우저에서 `http://서버IP:7860` 접속
- [ ] Flower: 브라우저에서 `http://서버IP:5556` 접속

#### 방화벽 설정 (외부 접속 필요 시)
- [ ] 포트 오픈: `sudo ufw allow 7860,8000,5556/tcp`

**모든 체크 완료 시 설치 성공! 🎉**

---

### 📝 새 서버 설치 체크리스트

설치 전에 다음 항목들을 확인하세요:

- [ ] OS: Ubuntu 20.04/22.04 또는 Debian 기반 시스템
- [ ] Python 3.12 설치 가능 여부 (또는 3.10 이상)
- [ ] 인터넷 연결 (패키지 다운로드용)
- [ ] sudo 권한 보유
- [ ] 디스크 공간: 최소 20GB 이상 권장
- [ ] GPU 사용 시: NVIDIA GPU 및 드라이버
- [ ] 네트워크: 방화벽에서 포트 6379, 7860, 8000, 5556 오픈 필요

### 방법 1: Docker 사용 (권장)

> **새로운 서버에 처음 설치하는 경우를 기준으로 작성되었습니다.**

#### 0. 시스템 준비 (Ubuntu/Debian 기준)

**기본 패키지 설치:**
```bash
# 시스템 업데이트
sudo apt-get update
sudo apt-get upgrade -y

# 필수 패키지 설치
sudo apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    python3.12 \
    python3.12-venv \
    python3-pip
```

**Docker 및 Docker Compose 설치:**
```bash
# Docker 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 현재 사용자를 docker 그룹에 추가 (sudo 없이 docker 실행)
sudo usermod -aG docker $USER

# Docker Compose 설치
sudo apt-get install -y docker-compose-plugin

# Docker 서비스 시작
sudo systemctl start docker
sudo systemctl enable docker

# 설치 확인
docker --version
docker compose version
```

**NVIDIA GPU 사용 시 (선택):**
```bash
# NVIDIA 드라이버 설치 (예: 535 버전)
sudo apt-get install -y nvidia-driver-535

# 재부팅
sudo reboot

# 드라이버 확인
nvidia-smi

# NVIDIA Container Toolkit 설치
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Docker 재시작
sudo systemctl restart docker

# GPU 접근 테스트
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

> **참고**: 로그아웃 후 다시 로그인해야 docker 그룹 권한이 적용됩니다.

#### 1. 프로젝트 클론
```bash
git clone https://github.com/junpyopark/medsam_project.git
cd medsam_project
```

#### 2. MedSAM2 저장소 클론
**⚠️ 필수: MedSAM2가 없으면 Docker 빌드가 실패합니다!**
```bash
# medsam_project 폴더 안에서 실행
git clone https://github.com/bowang-lab/MedSAM2.git

# 클론 확인
ls -la MedSAM2
# README.md, medsam2/ 등이 보여야 함
```

**디렉토리 구조 확인:**
```
medsam_project/
├── MedSAM2/          # ← 🔴 필수! Docker 빌드 시 이미지에 포함됨
│   ├── medsam2/
│   ├── README.md
│   └── setup.py
├── data/
├── models/
└── ...
```

> **중요**: 
> - **프로덕션 모드**: MedSAM2는 빌드 시 이미지에 포함되므로, 빌드 후 삭제 가능
> - **개발 모드**: MedSAM2가 볼륨 마운트되므로 항상 필요 (docker-compose.yml 수정 필요)
> - **빌드 전 체크**: `ls MedSAM2/setup.py` 명령어로 파일 존재 확인!

#### 3. 필요한 디렉토리 생성
```bash
# medsam_project 폴더 안에서 실행
mkdir -p data temp models

# 권한 설정 (필요시)
chmod 755 data temp models
```

#### 4. MedSAM2 모델 다운로드

**방법 1: 자동 다운로드 스크립트 (권장)**
```bash
# 프로젝트 루트에서 실행
chmod +x scripts/download_models.sh
./scripts/download_models.sh
```

**방법 2: 수동 다운로드**
```bash
cd models
wget https://huggingface.co/wanglab/MedSAM2/resolve/main/MedSAM2_latest.pt -O MedSAM2_latest.pt

# 다운로드 확인 (약 149MB여야 함)
ls -lh MedSAM2_latest.pt
```

**필요한 파일:**
- `MedSAM2_latest.pt` - MedSAM2 체크포인트 (149MB) ← 다운로드 필요
- `sam2.1_hiera_t512.yaml` - SAM2 설정 파일 (이미 포함됨) ✅

```plaintext
medsam_project/
└── models/
    ├── MedSAM2_latest.pt
    └── sam2.1_hiera_t512.yaml
```

#### 5. Docker Compose로 백엔드 실행
```bash
# Docker 이미지를 빌드하고 백엔드 서비스 실행
# 주의: 빌드에 시간이 오래 걸릴 수 있습니다 (10-20분)
docker compose up --build -d

# 빌드 진행 상황 확인 (별도 터미널)
docker compose logs -f api

# 빌드 완료 후 서비스 상태 확인
docker compose ps
# 모든 서비스가 "Up" 상태여야 함

# 전체 로그 확인
docker compose logs -f
```

**Docker Compose 서비스 구성:**
- **redis**: Redis 메시지 브로커 (포트 6380:6379, 호스트:컨테이너)
- **api**: FastAPI 서버 (포트 8000:8000, GPU 지원)
- **worker**: Celery Worker (GPU 처리, concurrency=2, 동시 2개 작업 처리)
- **monitor**: Flower 모니터링 대시보드 (포트 5556:5555)

> **중요 - 프로덕션 모드 vs 개발 모드**:
> 
> **현재 설정: 프로덕션 모드 (권장)**
> - MedSAM2와 코드가 Docker 이미지에 포함됨
> - 코드 수정 시 이미지 재빌드 필요: `docker compose up --build -d`
> - 안정적이고 배포에 적합
> 
> **개발 모드로 전환하려면**:
> `docker-compose.yml`에서 다음 줄의 주석을 해제:
> ```yaml
> volumes:
>   - ./MedSAM2:/app/MedSAM2              # 로컬 MedSAM2 사용
>   - ./medsam_api_server:/app/medsam_api_server  # 로컬 코드 사용
> ```
> - 코드 수정이 즉시 반영됨 (서비스 재시작만 필요)
> - 로컬에 MedSAM2가 클론되어 있어야 함

> **참고**: 
> - Redis는 Docker 내부에서 6379 포트, 호스트에서는 6380 포트로 접근합니다.
> - 모든 서비스는 GPU 컨테이너로 실행되며 NVIDIA GPU가 필요합니다.
> - 데이터, 모델, 임시 파일만 볼륨 마운트됩니다.

#### 6. Gradio 프론트엔드 실행 (로컬)
새 터미널에서:
```bash
# 가상환경 생성 및 활성화
python3.12 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r medsam_gradio_viewer/requirements.txt

# Gradio 앱 실행
python medsam_gradio_viewer/app.py
```

#### 7. 방화벽 설정 (선택)
외부에서 접속이 필요한 경우:
```bash
# UFW 사용 시
sudo ufw allow 7860/tcp  # Gradio
sudo ufw allow 8000/tcp  # FastAPI
sudo ufw allow 5556/tcp  # Flower
sudo ufw allow 6380/tcp  # Redis (Docker)

# 또는 특정 IP만 허용
sudo ufw allow from 192.168.1.0/24 to any port 7860
```

**완료!** 
- 로컬: http://127.0.0.1:7860
- 원격: http://서버IP:7860

---

### 🎛️ GPU 및 Worker 설정 (선택적 최적화)

#### GPU 선택 설정

특정 GPU만 사용하도록 제한할 수 있습니다. `docker-compose.yml` 파일을 수정하세요:

**예시: GPU 6번, 7번만 사용**
```yaml
api:
  environment:
    # ... 기존 설정 ...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['6']  # API 서버는 GPU 6번 사용
            capabilities: [gpu]

worker:
  environment:
    # ... 기존 설정 ...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['7']  # Worker는 GPU 7번 사용
            capabilities: [gpu]
```

**모든 GPU 사용 (기본값)**
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1  # 사용 가능한 GPU 중 1개 자동 할당
          capabilities: [gpu]
```

**GPU 할당 확인**
```bash
# API 컨테이너 GPU 확인
docker compose exec api nvidia-smi --query-gpu=index,name,pci.bus_id --format=csv

# Worker 컨테이너 GPU 확인
docker compose exec worker nvidia-smi --query-gpu=index,name,pci.bus_id --format=csv
```

#### Worker 성능 튜닝

동시 처리 작업 수를 조정하여 성능을 최적화할 수 있습니다.

**동시 처리 작업 수 설정**
```yaml
worker:
  command: celery -A medsam_api_server.celery_app:celery_app worker --loglevel=info --concurrency=2
```

**권장 설정:**
- `concurrency=1`: 순차 처리 (안정적, GPU 메모리 절약)
- `concurrency=2`: 2개 동시 처리 (권장, 대부분의 경우 충분)
- `concurrency=4-5`: 많은 동시 사용자 (GPU 메모리 충분한 경우)

**GPU 메모리 사용량 참고:**
- 2D 분할 1개: ~800 MB
- 3D 전파 1개: ~1,800 MB
- Concurrency=2 (3D 전파 2개 동시): ~2,700 MB

**적용 방법:**
```bash
# docker-compose.yml 수정 후
docker compose down
docker compose up -d

# 설정 확인
docker compose logs worker | grep concurrency
# 예상 출력: .> concurrency: 2 (prefork)
```

---

### 방법 2: 로컬 설치 (Docker 없이)

> **새로운 서버에 처음 설치하는 경우를 기준으로 작성되었습니다.**

#### 0. 시스템 준비 (Ubuntu/Debian 기준)

**기본 패키지 설치:**
```bash
# 시스템 업데이트
sudo apt-get update
sudo apt-get upgrade -y

# 필수 패키지 설치
sudo apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    redis-server

# Redis 시작 및 자동 시작 설정
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Redis 동작 확인
redis-cli ping  # 응답: PONG
```

**NVIDIA GPU 사용 시 (선택):**
```bash
# NVIDIA 드라이버 설치
sudo apt-get install -y nvidia-driver-535

# CUDA Toolkit 설치 (필요시)
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb
sudo apt-get update
sudo apt-get install -y cuda-toolkit-12-1

# 재부팅 후 확인
sudo reboot
nvidia-smi
```

#### 1. 프로젝트 클론 및 MedSAM2 설정
```bash
# 프로젝트 클론
git clone https://github.com/junpyopark/medsam_project.git
cd medsam_project

# MedSAM2 저장소 클론 (프로젝트 폴더 안)
git clone https://github.com/bowang-lab/MedSAM2.git
```

#### 2. 가상환경 설정 및 활성화
```bash
# medsam_project 폴더 안에서 실행
python3.12 -m venv .venv
source .venv/bin/activate

# pip 업그레이드
pip install --upgrade pip
```

#### 3. 필요한 디렉토리 생성
```bash
mkdir -p data temp models
chmod 755 data temp models
```

#### 4. 의존성 설치
```bash
# PyTorch 먼저 설치 (GPU 버전)
pip install torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121

# 또는 CPU 버전만 (GPU 없는 경우)
# pip install torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1

# 백엔드 의존성
pip install -r medsam_api_server/requirements.txt

# 프론트엔드 의존성
pip install -r medsam_gradio_viewer/requirements.txt
```

#### 5. MedSAM2 설치
```bash
# MedSAM2 디렉토리로 이동하여 설치
cd MedSAM2
pip install -e .
cd ..

# 설치 확인
python -c "import sam2; print('✅ MedSAM2 설치 완료')"
```

#### 6. 모델 다운로드 (로컬 방식)
```bash
# 방법 1: 자동 스크립트 (권장)
chmod +x scripts/download_models.sh
./scripts/download_models.sh

# 방법 2: 수동 다운로드
cd models
wget https://huggingface.co/wanglab/MedSAM2/resolve/main/MedSAM2_latest.pt -O MedSAM2_latest.pt
cd ..

# 다운로드 확인
ls -lh models/MedSAM2_latest.pt  # 약 149MB
```

#### 7. 스크립트 실행 권한 설정
```bash
chmod +x scripts/*.sh
```

#### 8. 서비스 시작
```bash
# 스크립트를 이용한 자동 시작
./scripts/start.sh

# 또는 수동 실행
# 터미널 1: FastAPI 서버
cd medsam_api_server
uvicorn main:app --host 0.0.0.0 --port 8000 &

# 터미널 2: Celery Worker
cd medsam_api_server
celery -A celery_app worker --loglevel=info &

# 터미널 3: Gradio UI
cd medsam_gradio_viewer
python app.py
```

#### 9. 방화벽 설정 (선택)
외부에서 접속이 필요한 경우:
```bash
# UFW 사용 시
sudo ufw allow 7860/tcp  # Gradio
sudo ufw allow 8000/tcp  # FastAPI
sudo ufw allow 5556/tcp  # Flower (선택)

# 또는 특정 IP만 허용
sudo ufw allow from 192.168.1.0/24 to any port 7860
```

**완료!** 이제 브라우저에서 `http://서버IP:7860` 으로 접속하세요.

---

## ✅ 설치 확인

설치가 완료되면 다음 명령어들로 정상 작동을 확인하세요:

### Docker 방식

#### 1단계: 컨테이너 상태 확인
```bash
docker compose ps

# 예상 출력:
# NAME              IMAGE              STATUS         PORTS
# medsam2_api       ...                Up             0.0.0.0:8000->8000/tcp
# medsam2_worker    ...                Up             
# medsam2_redis     redis:7-alpine     Up (healthy)   0.0.0.0:6380->6379/tcp
# medsam2_monitor   ...                Up             0.0.0.0:5556->5555/tcp
```

**문제 발생 시:**
- `Restarting` 상태: 로그 확인 `docker compose logs api`
- `Exit 1`: 빌드 오류, `docker compose up --build -d` 재실행
- `Unhealthy`: 헬스체크 실패, 서비스 시작 대기 (1-2분)

#### 2단계: API 서버 확인
```bash
curl http://localhost:8000/health

# 예상 출력:
# {
#   "success": true,
#   "message": "Service is healthy",
#   "system_info": { ... }
# }
```

#### 3단계: Redis 연결 확인
```bash
docker compose exec api redis-cli -h redis ping
# 예상 출력: PONG
```

#### 4단계: GPU 확인 (GPU 사용 시)
```bash
docker compose exec worker nvidia-smi

# GPU 정보가 표시되어야 함
# 에러 발생 시: GPU 설정 문제
```

#### 5단계: MedSAM2 모듈 확인
```bash
docker compose exec worker python -c "import sam2; print('✅ MedSAM2 loaded')"

# 예상 출력: ✅ MedSAM2 loaded
# ImportError 발생 시: 빌드 문제
```

#### 6단계: Gradio UI 확인
```bash
curl -s http://localhost:7860 | head -20
# HTML 응답이 와야 함 (<!DOCTYPE html>...)

# 또는 브라우저에서
# http://서버IP:7860
```

### 로컬 방식
```bash
# Redis 확인
redis-cli ping
# PONG 응답이 와야 함

# API 서버 확인
curl http://localhost:8000/health

# GPU 확인 (GPU 사용 시)
nvidia-smi

# 서비스 상태 확인
./scripts/status.sh
```

### 웹 브라우저 확인
1. **Gradio UI**: http://서버IP:7860 - 업로드 화면이 보여야 함
2. **API 문서**: http://서버IP:8000/docs - Swagger UI가 열려야 함
3. **Flower**: http://서버IP:5556 - Celery 대시보드가 보여야 함

---

## 🔧 사용법

### 워크플로우 상세

#### 1. 파일 업로드 단계
1. 사용자가 NIfTI 파일 업로드
2. Gradio가 파일을 FastAPI로 전송
3. FastAPI가 고유 job_id 생성 및 파일 저장 (`data/{job_id}/`)
4. job_id를 Gradio State에 저장

#### 2. 2D 분할 단계
1. 사용자가 슬라이스 선택 및 좌표 입력
2. Gradio가 좌표를 서버 좌표계로 변환 (`_display_to_original_xy()`)
3. FastAPI가 Celery 작업 큐에 2D 분할 작업 등록
4. Celery Worker가 MedSAM2 모델로 분할 수행
5. Gradio가 폴링(3초 간격, 최대 6분)으로 완료 대기 후 결과 표시

#### 3. 3D Propagation 단계
1. 사용자가 3D Propagation 실행
2. FastAPI가 Celery 작업 큐에 3D 전파 작업 등록
3. Celery Worker가 양방향 전파 수행
4. Gradio가 진행률 표시(3초 간격, 최대 3시간) 및 완료 시 다운로드 링크 제공

### 주요 기능 설명

#### 좌표 변환
- **표시 좌표**: 90도 회전된 이미지 기준 (UI에서 보이는 대로)
- **서버 좌표**: 원본 이미지 기준 (실제 NIfTI 파일)
- **변환 함수**: `_display_to_original_xy()` 자동 처리

#### 폴링 메커니즘
- **2D 분할**: 3초 간격, 최대 120회 (6분)
- **3D 전파**: 3초 간격, 최대 3600회 (3시간)

---

## 📁 프로젝트 구조

```
medsam_project/
├── MedSAM2/                       # MedSAM2 저장소 (별도 클론 필요)
├── data/                          # 업로드된 원본 NIfTI 파일 ({job_id}/ 별로 저장)
├── temp/                          # 생성된 마스크, 임시 파일
├── models/                        # MedSAM2 모델 가중치 (.pt, .yaml)
├── medsam_gradio_viewer/          # 프론트엔드 (Gradio)
│   ├── app.py                     # 메인 UI 애플리케이션
│   └── requirements.txt           # 프론트엔드 의존성
├── medsam_api_server/             # 백엔드 (FastAPI + Celery)
│   ├── Dockerfile                 # Docker 설정
│   ├── api/                       # API 라우터
│   │   └── v1/
│   │       ├── jobs.py            # 작업 관리 엔드포인트
│   │       └── system.py          # 시스템 모니터링 엔드포인트
│   ├── core/                      # 핵심 모듈
│   │   ├── gpu_manager.py         # GPU 자원 관리
│   │   └── model_manager.py       # MedSAM2 모델 관리
│   ├── schemas/                   # Pydantic 데이터 모델
│   │   └── api_models.py          # API 요청/응답 스키마
│   ├── tasks/                     # Celery 작업
│   │   └── segmentation.py        # 분할 작업 정의
│   ├── static/                    # 정적 파일
│   ├── celery_app.py              # Celery 설정
│   ├── main.py                    # FastAPI 애플리케이션
│   ├── worker.sh                  # Celery 워커 실행 스크립트
│   └── requirements.txt           # 백엔드 의존성
├── scripts/                       # 관리 스크립트
│   ├── start.sh                   # 모든 서비스 시작
│   ├── stop.sh                    # 모든 서비스 중지
│   ├── restart.sh                 # 서비스 재시작
│   ├── status.sh                  # 서비스 상태 확인
│   ├── logs.sh                    # 로그 확인
│   └── download_models.sh         # 모델 자동 다운로드
├── docker-compose.yml             # Docker Compose 설정 (redis, api, worker, monitor)
├── .gitignore                     # Git 제외 파일
└── README.md                      # 이 파일
```

### 주요 코드 구조

#### 프론트엔드 (`medsam_gradio_viewer/app.py`)
```python
# 주요 함수들
def load_nifti(fileobj):           # NIfTI 파일 로드
def show_slice(state, slice_index): # 슬라이스 표시
def trigger_segmentation():        # 2D 분할 트리거
def poll_segmentation():           # 2D 분할 폴링
def trigger_propagation():         # 3D 전파 트리거
def poll_propagation():            # 3D 전파 폴링
```

#### 백엔드 API (`medsam_api_server/api/v1/`)
```python
# jobs.py - 작업 관리 엔드포인트
@router.post("")                        # 작업 생성 (파일 업로드)
@router.post("/{job_id}/initial-mask")  # 2D 초기 마스크 생성
@router.post("/{job_id}/propagate")     # 3D 전파
@router.get("/{job_id}/status")         # 상태 조회
@router.get("/{job_id}/result")         # 결과 다운로드
@router.delete("/{job_id}")             # 작업 삭제

# system.py - 시스템 모니터링 엔드포인트
@router.get("/status")                  # 시스템 상태
@router.get("/gpu")                     # GPU 정보
@router.get("/jobs/active")             # 활성 작업 목록
@router.get("/model")                   # 모델 정보
@router.post("/model/reload")           # 모델 재로딩
@router.post("/cleanup")                # 정리
```

#### Celery 작업 (`medsam_api_server/tasks/segmentation.py`)
```python
# 주요 작업들
@celery_app.task
def run_2d_segmentation():          # 2D 분할 작업
@celery_app.task
def run_3d_propagation():           # 3D 전파 작업
```

---

## 🔌 API 엔드포인트

### 작업 관리
- `POST /api/v1/jobs` - 새 작업 생성 (NIfTI 파일 업로드)
- `GET /api/v1/jobs/{job_id}/status` - 작업 상태 조회 (진행률 포함)
- `GET /api/v1/jobs/{job_id}/result` - 결과 파일 다운로드 (2D 마스크 PNG 또는 3D 마스크 NIfTI)
- `DELETE /api/v1/jobs/{job_id}` - 작업 삭제 (파일 및 메타데이터 제거)

### 분할 작업
- `POST /api/v1/jobs/{job_id}/initial-mask` - 2D 초기 마스크 생성 (특정 슬라이스에 대해)
- `POST /api/v1/jobs/{job_id}/propagate` - 3D Propagation 실행 (2D 마스크 기반 전체 볼륨 전파)

### 시스템 모니터링
- `GET /health` - API 서버 헬스체크 (GPU, 메모리, 업타임 정보 포함)
- `GET /api/v1/system/status` - 시스템 상세 상태 (CPU, 메모리, GPU 사용량)
- `GET /api/v1/system/gpu` - GPU 정보 및 사용 현황
- `GET /api/v1/system/jobs/active` - 현재 활성 작업 목록
- `GET /api/v1/system/model` - 로드된 모델 정보
- `POST /api/v1/system/model/reload` - 모델 재로딩
- `POST /api/v1/system/cleanup` - 임시 파일 정리

자세한 API 명세는 서버 실행 후 http://127.0.0.1:8000/docs 에서 확인할 수 있습니다.

---

## 💻 개발 가이드

### 서비스 관리 명령어

```bash
# 모든 서비스 시작
./scripts/start.sh

# 모든 서비스 중지
./scripts/stop.sh

# 모든 서비스 재시작
./scripts/restart.sh

# 특정 서비스만 재시작
./scripts/restart.sh gradio
./scripts/restart.sh api
./scripts/restart.sh celery

# 서비스 상태 확인
./scripts/status.sh

# 로그 확인
./scripts/logs.sh              # 모든 로그
./scripts/logs.sh api          # API 로그만
./scripts/logs.sh celery       # Celery 로그만
./scripts/logs.sh gradio       # Gradio 로그만
```

### Docker 사용 시

```bash
# 모든 서비스 시작
docker compose up -d

# 모든 서비스 중지
docker compose down

# 서비스 상태 확인
docker compose ps

# 실시간 로그 확인
docker compose logs -f

# 특정 서비스 로그 확인
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f redis
```

### 코드 수정 후 재시작

#### 로컬 개발 시
```bash
# 프론트엔드 수정 후
./scripts/restart.sh gradio

# 백엔드 API 수정 후
./scripts/restart.sh api

# Celery 작업 수정 후
./scripts/restart.sh celery
```
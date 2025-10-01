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
                                   │   (AI Processing)│
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
- Python 3.10+
- Redis 서버
- 가상환경 (권장)

**선택 (AI 처리 가속화):**
- NVIDIA GPU (CUDA 지원)
- NVIDIA 드라이버
- CUDA Toolkit
- NVIDIA Container Toolkit (Docker 사용 시)

### 1. 서비스 시작
```bash
cd /home/junpyo/projects/medsam_project

# 가상환경 활성화 (필요시)
source .venv/bin/activate

# 모든 서비스 시작 (Redis, FastAPI, Celery, Gradio)
./scripts/start.sh
```

### 2. 웹 접속
- **Gradio UI** (사용자 인터페이스): http://127.0.0.1:7860
- **API 서버** (루트): http://127.0.0.1:8000
- **API 문서** (Swagger UI): http://127.0.0.1:8000/docs
- **API 문서** (ReDoc): http://127.0.0.1:8000/redoc
- **Health Check**: http://127.0.0.1:8000/health
- **Celery 모니터** (Flower): http://127.0.0.1:5556

### 3. 기본 사용 흐름

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

### 방법 1: Docker 사용 (권장)

#### 1. 프로젝트 클론
```bash
git clone https://github.com/junpyopark/medsam_project.git
cd medsam_project
```

#### 2. MedSAM2 모델 다운로드

**자동 다운로드 (권장)**
```bash
./scripts/download_models.sh
```

**수동 다운로드**
[MedSAM2 공식 저장소](https://github.com/bowang-lab/MedSAM2)를 참고하여 다음 파일들을 다운로드하세요:
- `MedSAM2_latest.pt` - MedSAM2 체크포인트
- `sam2.1_hiera_t512.yaml` - SAM2 설정 파일

```plaintext
medsam_project/
└── models/
    ├── MedSAM2_latest.pt
    └── sam2.1_hiera_t512.yaml
```

#### 3. Docker Compose로 백엔드 실행
```bash
# Docker 이미지를 빌드하고 백엔드 서비스 실행
docker-compose up --build -d

# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f
```

**Docker Compose 서비스 구성:**
- **redis**: Redis 메시지 브로커 (포트 6380:6379, 호스트:컨테이너)
- **api**: FastAPI 서버 (포트 8000:8000, GPU 지원)
- **worker**: Celery Worker (GPU 처리, concurrency=1)
- **monitor**: Flower 모니터링 대시보드 (포트 5556:5555)

> **참고**: 
> - Redis는 Docker 내부에서 6379 포트, 호스트에서는 6380 포트로 접근합니다.
> - 모든 서비스는 GPU 컨테이너로 실행되며 NVIDIA GPU가 필요합니다.
> - 볼륨 마운트를 통해 `data/`, `models/`, `temp/` 디렉토리를 공유합니다.

#### 4. Gradio 프론트엔드 실행 (로컬)
새 터미널에서:
```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r medsam_gradio_viewer/requirements.txt

# Gradio 앱 실행
python medsam_gradio_viewer/app.py
```

### 방법 2: 로컬 설치

#### 1. 가상환경 설정
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 또는
.venv\Scripts\activate     # Windows
```

#### 2. 의존성 설치
```bash
# 백엔드 의존성
pip install -r medsam_api_server/requirements.txt

# 프론트엔드 의존성
pip install -r medsam_gradio_viewer/requirements.txt
```

#### 3. Redis 설치 및 실행
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS (Homebrew)
brew install redis
brew services start redis

# 또는 Docker로 실행
docker run -d -p 6379:6379 redis:alpine
```

#### 4. 서비스 시작
```bash
# 모든 서비스 시작
./scripts/start.sh

# 또는 개별 실행
# Redis가 이미 실행 중이라면
cd medsam_api_server
uvicorn main:app --host 0.0.0.0 --port 8000 &
celery -A celery_app worker --loglevel=info &

cd ../medsam_gradio_viewer
python app.py
```

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
├── MedSAM2/                       # MedSAM2 Git Submodule
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
docker-compose up -d

# 모든 서비스 중지
docker-compose down

# 서비스 상태 확인
docker-compose ps

# 실시간 로그 확인
docker-compose logs -f

# 특정 서비스 로그 확인
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f redis
```

### 코드 수정 후 재시작

```bash
# 프론트엔드 수정 후
./scripts/restart.sh gradio

# 백엔드 API 수정 후
./scripts/restart.sh api

# Celery 작업 수정 후
./scripts/restart.sh celery

# Docker 사용 시
docker-compose restart api
docker-compose restart worker
```

### 디버깅

```bash
# 실시간 로그 모니터링
./scripts/logs.sh all 100 | grep -i error

# 특정 서비스만 모니터링
tail -f /tmp/api.log | grep -i error
tail -f /tmp/celery.log | grep -i error

# 프로세스 확인
ps aux | grep -E '(uvicorn|celery|gradio)'

# 포트 사용 확인
netstat -tlnp | grep -E ':(6379|8000|7860|5556)'
```

### 시스템 모니터링

```bash
# Flower를 통한 Celery 모니터링
open http://127.0.0.1:5556  # 또는 브라우저에서 접속

# API를 통한 시스템 상태 확인
curl http://127.0.0.1:8000/health | jq
curl http://127.0.0.1:8000/api/v1/system/status | jq
curl http://127.0.0.1:8000/api/v1/system/gpu | jq
curl http://127.0.0.1:8000/api/v1/system/jobs/active | jq

# GPU 사용량 확인
nvidia-smi  # 로컬
docker exec medsam2_worker nvidia-smi  # Docker
```

### 기여 가이드

#### 브랜치 전략
1. 새 브랜치 생성: `git checkout -b feature/새기능명`
2. 코드 수정 및 테스트
3. 커밋: `git commit -m "feat: 새 기능 추가"`
4. 메인 브랜치로 병합

#### 테스트 절차
```bash
# 서비스 재시작
./scripts/restart.sh

# 로그 확인
./scripts/logs.sh

# 상태 확인
./scripts/status.sh

# 기능 테스트
# 1. Gradio UI 접속 (http://127.0.0.1:7860)
# 2. 파일 업로드 테스트
# 3. 2D 분할 테스트
# 4. 3D 전파 테스트
```

---

## 🔍 문제 해결

### 서비스가 시작되지 않는 경우

```bash
# 상태 확인
./scripts/status.sh

# 로그 확인
./scripts/logs.sh

# 강제 재시작
./scripts/stop.sh
./scripts/start.sh

# 프로세스 강제 종료
sudo kill -9 $(pgrep -f uvicorn)
sudo kill -9 $(pgrep -f celery)
sudo kill -9 $(pgrep -f gradio)
```

### 포트 충돌 시

```bash
# 포트 사용 확인
netstat -tlnp | grep -E ':(6379|6380|8000|7860|5556)'

# 특정 포트 사용 프로세스 확인
lsof -i :8000   # FastAPI
lsof -i :7860   # Gradio
lsof -i :6379   # Redis (로컬)
lsof -i :6380   # Redis (Docker)
lsof -i :5556   # Flower

# 프로세스 종료
sudo kill -9 <PID>
```

### Redis 연결 오류

```bash
# Redis 상태 확인
redis-cli ping
# 응답: PONG (정상)

# Redis 재시작
sudo systemctl restart redis

# Redis 로그 확인
sudo journalctl -u redis -n 50

# Docker 사용 시
docker-compose restart redis
docker-compose logs -f redis
```

### 파일 업로드 실패

- NIfTI 파일 형식 확인 (.nii.gz)
- 파일 크기 확인 (너무 큰 파일은 시간 소요)
- `data/` 디렉토리 권한 확인
- API 서버 로그 확인: `tail -f /tmp/api.log`

### 분할 실패

- 좌표 범위 확인 (이미지 크기 내)
- GPU 메모리 확인 (CUDA out of memory)
- Celery Worker 로그 확인: `tail -f /tmp/celery.log`
- 모델 파일 존재 확인: `ls -la models/`

### Gradio 접속 불가

```bash
# 포트 7860이 사용 중인지 확인
lsof -i :7860

# 방화벽 설정 확인
sudo ufw status

# Gradio 로그 확인
tail -f /tmp/gradio.log

# 프로세스 확인
ps aux | grep gradio
```

**참고**: 
- 현재 Gradio는 `share=False`로 설정되어 로컬 접속만 가능합니다.
- 외부 접속이 필요한 경우 `medsam_gradio_viewer/app.py`에서 `share=True`로 변경하세요.
- `share=True` 활성화 시 Gradio가 자동으로 공개 URL을 생성합니다.

### Docker 관련 문제

```bash
# Docker 이미지 재빌드
docker-compose build --no-cache

# 볼륨 마운트 확인
docker-compose config

# 컨테이너 내부 접속
docker-compose exec api bash
docker-compose exec worker bash

# 컨테이너 로그 실시간 확인
docker-compose logs -f worker

# NVIDIA GPU 설정 확인
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Redis 연결 테스트 (Docker)
docker-compose exec api redis-cli -h redis ping
```

### GPU 관련 문제

```bash
# GPU 사용 가능 여부 확인
nvidia-smi

# Docker에서 GPU 접근 확인
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# NVIDIA Container Toolkit 설치 확인
dpkg -l | grep nvidia-container-toolkit

# GPU 메모리 부족 시
# docker-compose.yml에서 GPU_MEMORY_LIMIT 값 조정 (예: 0.6)
# 또는 MAX_CONCURRENT_JOBS 값을 1로 감소

# Worker 컨테이너에서 GPU 확인
docker-compose exec worker nvidia-smi
docker-compose exec worker python -c "import torch; print(torch.cuda.is_available())"
```

### 일반적인 문제 체크리스트

1. ✅ Redis 서버가 실행 중인가? (`redis-cli ping` 또는 `docker-compose ps`)
2. ✅ 가상환경이 활성화되어 있는가? (로컬 실행 시)
3. ✅ 모든 의존성이 설치되어 있는가?
4. ✅ 포트가 이미 사용 중이지 않은가? (6379/6380, 8000, 7860, 5556)
5. ✅ 필요한 디렉토리(`data/`, `temp/`, `models/`)가 존재하는가?
6. ✅ 모델 파일이 올바른 위치에 있는가? (`models/MedSAM2_latest.pt`, `models/sam2.1_hiera_t512.yaml`)
7. ✅ 로그 파일에 에러 메시지가 있는가?
8. ✅ GPU가 사용 가능한가? (`nvidia-smi` 실행 확인)
9. ✅ Docker를 사용 중이라면 모든 컨테이너가 정상 실행 중인가? (`docker-compose ps`)
10. ✅ API 서버가 정상 응답하는가? (`curl http://127.0.0.1:8000/health`)

### 서비스 완전 정리

```bash
# 모든 서비스 중지
./scripts/stop.sh

# 로그 파일 정리
rm -f /tmp/api.log /tmp/celery.log /tmp/gradio.log

# 데이터 정리 (주의: 업로드된 파일 삭제됨!)
rm -rf data/*
rm -rf temp/*

# Docker 사용 시
docker-compose down -v  # 볼륨까지 삭제
docker system prune -a  # 미사용 이미지/컨테이너 정리
```

---

## 🔧 주요 기술 스택

### 프론트엔드
- **Gradio 4.44.1**: 웹 UI 프레임워크
- **NumPy**: 수치 계산
- **Nibabel**: NIfTI 파일 처리

### 백엔드
- **FastAPI**: 웹 API 프레임워크
- **Celery**: 비동기 작업 큐
- **Redis 7**: 메시지 브로커 및 캐시
- **Uvicorn**: ASGI 서버
- **Pydantic**: 데이터 검증 및 설정 관리
- **Flower**: Celery 모니터링 대시보드

### 의료영상 처리
- **MedSAM2**: 의료영상 분할 AI 모델 (3D/4D 분할)
- **PyTorch**: 딥러닝 프레임워크
- **Nibabel**: NIfTI 파일 읽기/쓰기
- **SimpleITK**: 의료 영상 처리
- **NumPy**: 배열 연산
- **SciPy**: 과학 계산

### 인프라
- **Docker & Docker Compose**: 컨테이너화 및 오케스트레이션
- **NVIDIA Container Toolkit**: GPU 지원
- **CUDA**: GPU 가속

---

## 🚨 주의사항

### 파일 처리
- **입력**: NIfTI (.nii.gz) 파일만 지원
- **출력**: 3D 마스크 (.nii.gz) 파일
- **저장**: `data/{job_id}/` 디렉토리에 저장
- **보안**: 민감한 의료 데이터는 적절한 보안 조치 필요

### 좌표 시스템
- **표시 좌표**: 90도 회전된 이미지 기준 (UI)
- **서버 좌표**: 원본 이미지 기준 (백엔드)
- **자동 변환**: 프론트엔드에서 자동 처리

### 성능 최적화
- GPU 사용 시 처리 속도 향상
- 대용량 파일은 처리 시간 증가
- Celery Worker 수를 조절하여 병렬 처리 가능

### 환경 변수 설정
Docker Compose 또는 로컬 실행 시 다음 환경 변수를 설정할 수 있습니다:

**필수 환경 변수:**
- `CELERY_BROKER_URL`: Redis 브로커 URL (기본값: `redis://localhost:6379/0`)
- `CELERY_RESULT_BACKEND`: Redis 결과 백엔드 URL (기본값: `redis://localhost:6379/1`)
- `DATA_ROOT`: 업로드 파일 저장 경로 (기본값: `/app/data`)
- `MODEL_ROOT`: 모델 파일 경로 (기본값: `/app/models`)
- `TEMP_ROOT`: 임시 파일 경로 (기본값: `/app/temp`)

**선택 환경 변수:**
- `GPU_MEMORY_LIMIT`: GPU 메모리 사용량 제한 (기본값: `0.8`, 80%)
- `MAX_CONCURRENT_JOBS`: 동시 처리 작업 수 (기본값: `2`)
- `CORS_ORIGIN`: CORS 허용 오리진 (기본값: `*`)

---

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

---

## 💡 사용 팁

### 최적의 성능을 위한 권장 사항

1. **좌표 선택**: 관심 영역(ROI)을 명확하게 포함하도록 충분히 큰 경계 상자를 그리되, 너무 크면 정확도가 떨어질 수 있습니다.
2. **슬라이스 선택**: 관심 영역이 가장 명확하게 보이는 중간 슬라이스를 선택하세요.
3. **GPU 메모리**: 메모리 부족 오류가 발생하면 `GPU_MEMORY_LIMIT`를 0.6 이하로 줄이세요.
4. **동시 작업**: 여러 작업을 동시에 실행하면 GPU 메모리가 부족할 수 있으므로 `MAX_CONCURRENT_JOBS=1`로 설정하세요.
5. **모니터링**: Flower 대시보드(http://127.0.0.1:5556)에서 실시간으로 작업 상태를 확인할 수 있습니다.

### 일반적인 워크플로우

```
1. NIfTI 파일 업로드
   ↓
2. 슬라이스 탐색 (슬라이더 사용)
   ↓
3. 관심 영역에 경계 상자 지정 (x1, y1, x2, y2)
   ↓
4. 2D 분할 실행 및 확인
   ↓
5. 3D Propagation 실행
   ↓
6. 결과 다운로드 및 검토
```

---

## 📞 지원 및 기여

- **Issues**: GitHub Issues를 통해 버그 리포트 및 기능 제안
- **Pull Requests**: 기여를 환영합니다
- **공식 MedSAM2**: [GitHub Repository](https://github.com/bowang-lab/MedSAM2)

---

## 📚 참고 자료

- [MedSAM2 논문](https://github.com/bowang-lab/MedSAM2) - 공식 GitHub 저장소
- [FastAPI 문서](https://fastapi.tiangolo.com/) - FastAPI 공식 문서
- [Celery 문서](https://docs.celeryq.dev/) - Celery 공식 문서
- [Gradio 문서](https://www.gradio.app/docs/) - Gradio 공식 문서

---
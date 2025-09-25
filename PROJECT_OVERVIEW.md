# 🏥 MedSAM2 HITL 프로젝트 개요

## 📋 프로젝트 소개

**MedSAM2 HITL (Human-in-the-Loop) 3D 의료영상 분할 시스템**

이 프로젝트는 의료영상에서 병변을 자동으로 분할하는 AI 시스템으로, 의사가 중간에 개입하여 정확도를 높이는 Human-in-the-Loop 방식으로 구현되었습니다.

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

## 📁 프로젝트 구조

```
medsam_project/
├── medsam_gradio_viewer/          # 프론트엔드
│   ├── app.py                     # 메인 UI 애플리케이션
│   └── requirements.txt           # 프론트엔드 의존성
├── medsam_api_server/             # 백엔드
│   ├── api/v1/jobs.py            # API 엔드포인트
│   ├── tasks/segmentation.py     # Celery 작업 정의
│   ├── celery_app.py             # Celery 설정
│   ├── main.py                   # FastAPI 앱
│   └── requirements.txt          # 백엔드 의존성
├── scripts/                       # 관리 스크립트
│   ├── start.sh                  # 서비스 시작
│   ├── stop.sh                   # 서비스 중지
│   ├── restart.sh                # 서비스 재시작
│   ├── status.sh                 # 상태 확인
│   └── logs.sh                   # 로그 확인
├── data/                         # 데이터 저장소
├── README.md                     # 전체 문서
├── QUICK_START.md                # 빠른 시작 가이드
├── GIT_GUIDE.md                  # Git 사용법
└── PROJECT_OVERVIEW.md           # 이 파일
```

## 🔌 API 엔드포인트

### 작업 관리
- `POST /api/v1/jobs` - 새 작업 생성 (NIfTI 파일 업로드)
- `GET /api/v1/jobs/{job_id}/status` - 작업 상태 조회
- `GET /api/v1/jobs/{job_id}/result` - 결과 파일 다운로드

### 분할 작업
- `POST /api/v1/jobs/{job_id}/segment-2d` - 2D 분할 실행
- `POST /api/v1/jobs/{job_id}/propagate` - 3D Propagation 실행

## 🔄 워크플로우

### 1. 파일 업로드
1. 사용자가 NIfTI 파일 업로드
2. Gradio가 파일을 FastAPI로 전송
3. FastAPI가 고유 job_id 생성 및 파일 저장
4. job_id를 Gradio State에 저장

### 2. 2D 분할
1. 사용자가 슬라이스 선택 및 좌표 입력
2. Gradio가 좌표를 서버 좌표계로 변환
3. FastAPI가 Celery 작업 큐에 2D 분할 작업 등록
4. Celery Worker가 MedSAM2 모델로 분할 수행
5. Gradio가 폴링으로 완료 대기 후 결과 표시

### 3. 3D Propagation
1. 사용자가 3D Propagation 실행
2. FastAPI가 Celery 작업 큐에 3D 전파 작업 등록
3. Celery Worker가 양방향 전파 수행
4. Gradio가 진행률 표시 및 완료 시 다운로드 링크 제공

## 🛠️ 개발 환경 설정

### 필수 요구사항
- Python 3.10+
- Redis 서버
- 가상환경 (권장)

### 설치 및 실행
```bash
# 1. 가상환경 활성화
source .venv/bin/activate

# 2. 의존성 설치
pip install -r medsam_api_server/requirements.txt
pip install -r medsam_gradio_viewer/requirements.txt

# 3. Redis 시작
sudo systemctl start redis

# 4. 모든 서비스 시작
./scripts/start.sh
```

### 접속 URL
- **Gradio UI**: http://127.0.0.1:7860
- **API 서버**: http://127.0.0.1:8000
- **API 문서**: http://127.0.0.1:8000/docs

## 🔧 주요 기술 스택

### 프론트엔드
- **Gradio 4.44.1**: 웹 UI 프레임워크
- **NumPy**: 수치 계산
- **Nibabel**: NIfTI 파일 처리

### 백엔드
- **FastAPI**: 웹 API 프레임워크
- **Celery**: 비동기 작업 큐
- **Redis**: 메시지 브로커 및 캐시
- **Uvicorn**: ASGI 서버

### 의료영상 처리
- **Nibabel**: NIfTI 파일 읽기/쓰기
- **NumPy**: 배열 연산
- **SciPy**: 과학 계산

## 📝 코드 구조 설명

### 프론트엔드 (`medsam_gradio_viewer/app.py`)
```python
# 주요 함수들
def load_nifti(fileobj):           # NIfTI 파일 로드
def show_slice(state, slice_index): # 슬라이스 표시
def trigger_segmentation():        # 2D 분할 트리거
def poll_segmentation():           # 2D 분할 폴링
def trigger_propagation():         # 3D 전파 트리거
def poll_propagation():            # 3D 전파 폴링
```

### 백엔드 API (`medsam_api_server/api/v1/jobs.py`)
```python
# 주요 엔드포인트
@router.post("")                   # 작업 생성
@router.post("/{job_id}/segment-2d") # 2D 분할
@router.post("/{job_id}/propagate")  # 3D 전파
@router.get("/{job_id}/status")    # 상태 조회
@router.get("/{job_id}/result")    # 결과 다운로드
```

### Celery 작업 (`medsam_api_server/tasks/segmentation.py`)
```python
# 주요 작업들
@celery_app.task
def run_2d_segmentation():         # 2D 분할 작업
@celery_app.task
def run_3d_propagation():          # 3D 전파 작업
```

## 🚨 주의사항

### 파일 처리
- **입력**: NIfTI (.nii.gz) 파일만 지원
- **출력**: 3D 마스크 (.nii.gz) 파일
- **저장**: `data/{job_id}/` 디렉토리에 저장

### 좌표 변환
- **표시 좌표**: 90도 회전된 이미지 기준
- **서버 좌표**: 원본 이미지 기준
- **변환 함수**: `_display_to_original_xy()`

### 폴링 메커니즘
- **2D 분할**: 3초 간격, 최대 120회 (6분)
- **3D 전파**: 3초 간격, 최대 3600회 (3시간)

## 🔍 디버깅 가이드

### 로그 확인
```bash
# 모든 로그
./scripts/logs.sh

# 특정 서비스 로그
./scripts/logs.sh api
./scripts/logs.sh celery
./scripts/logs.sh gradio
```

### 상태 확인
```bash
# 서비스 상태
./scripts/status.sh

# 프로세스 확인
ps aux | grep -E '(uvicorn|celery|gradio)'
```

### 일반적인 문제
1. **Redis 연결 오류**: Redis 서버 상태 확인
2. **포트 충돌**: 기존 프로세스 종료 후 재시작
3. **파일 업로드 실패**: NIfTI 파일 형식 확인
4. **분할 실패**: 좌표 범위 및 이미지 크기 확인

## 📚 추가 자료

- **README.md**: 전체 프로젝트 문서
- **QUICK_START.md**: 빠른 시작 가이드
- **GIT_GUIDE.md**: Git 사용법
- **API 문서**: http://127.0.0.1:8000/docs

## 🤝 기여 가이드

### 코드 수정 시
1. 새 브랜치 생성: `git checkout -b feature/새기능명`
2. 코드 수정 및 테스트
3. 커밋: `git commit -m "feat: 새 기능 추가"`
4. 메인 브랜치로 병합

### 테스트
```bash
# 서비스 재시작
./scripts/restart.sh

# 로그 확인
./scripts/logs.sh

# 상태 확인
./scripts/status.sh
```

이 문서를 통해 새로운 개발자가 프로젝트를 빠르게 이해하고 기여할 수 있습니다.

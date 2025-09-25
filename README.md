# MedSAM2 HITL 3D 뷰어 & API 서버

MedSAM2를 활용한 Human-in-the-Loop(HITL) 3D 의료영상 분할 애플리케이션입니다. 프론트엔드(Gradio)와 백엔드(FastAPI + Celery + Redis)가 분리된 구조로 구현되어 있습니다.

## 🏗️ 아키텍처

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
                                   │  Celery Worker  │
                                   │ (AI Processing) │
                                   └─────────────────┘
```

## 🚀 빠른 시작

### 1. 서비스 시작
```bash
# 모든 서비스 시작 (Redis, FastAPI, Celery, Gradio)
./scripts/start.sh

# 또는 개별 서비스 시작
./scripts/start.sh redis    # Redis만 시작
./scripts/start.sh api      # FastAPI만 시작
./scripts/start.sh celery   # Celery만 시작
./scripts/start.sh gradio   # Gradio만 시작
```

### 2. 서비스 중지
```bash
# 모든 서비스 중지
./scripts/stop.sh

# 또는 개별 서비스 중지
./scripts/stop.sh api       # FastAPI만 중지
./scripts/stop.sh celery    # Celery만 중지
./scripts/stop.sh gradio    # Gradio만 중지
```

### 3. 웹 접속
- **Gradio UI**: http://127.0.0.1:7860
- **API 서버**: http://127.0.0.1:8000
- **API 문서**: http://127.0.0.1:8000/docs

## 📋 사전 요구사항

- Python 3.10+
- Redis 서버
- 가상환경 (권장)

## 🛠️ 설치

### 1. 프로젝트 클론 및 가상환경 설정
```bash
git clone <repository-url>
cd medsam_project

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 또는
.venv\Scripts\activate     # Windows
```

### 2. 의존성 설치
```bash
# 백엔드 의존성
pip install -r medsam_api_server/requirements.txt

# 프론트엔드 의존성
pip install -r medsam_gradio_viewer/requirements.txt
```

### 3. Redis 설치 및 실행
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

## 📁 프로젝트 구조

```
medsam_project/
├── medsam_gradio_viewer/          # 프론트엔드 (Gradio)
│   ├── app.py                     # 메인 UI 애플리케이션
│   └── requirements.txt           # 프론트엔드 의존성
├── medsam_api_server/             # 백엔드 (FastAPI)
│   ├── api/v1/jobs.py            # API 엔드포인트
│   ├── tasks/segmentation.py     # Celery 작업 정의
│   ├── celery_app.py             # Celery 설정
│   ├── main.py                   # FastAPI 앱
│   ├── worker.sh                 # Celery 워커 실행 스크립트
│   ├── Dockerfile                # Docker 설정
│   └── requirements.txt          # 백엔드 의존성
├── scripts/                       # 관리 스크립트
│   ├── start.sh                  # 서비스 시작
│   └── stop.sh                   # 서비스 중지
├── data/                         # 데이터 저장소
└── README.md                     # 이 파일
```

## 🔧 사용법

### 1. NIfTI 파일 업로드
1. 웹 브라우저에서 http://127.0.0.1:7860 접속
2. "NIfTI (.nii.gz) 업로드"에서 3D 의료영상 파일 선택
3. "새 작업 시작" 버튼 클릭하여 백엔드에 작업 생성

### 2. 2D 분할 (중간 슬라이스)
1. 슬라이더를 조정하여 원하는 슬라이스로 이동
2. x1, y1, x2, y2 텍스트 박스에 분할할 영역의 좌표 입력
3. "중간 슬라이스 2D 분할" 버튼 클릭
4. 자동 폴링으로 완료까지 대기 (약 3초 간격)
5. 완료 시 빨간색 마스크가 이미지에 오버레이됨

### 3. 3D Propagation
1. 시작/끝 슬라이스 범위 설정 (기본값: 전체 범위)
2. "3D Propagation 실행" 버튼 클릭
3. 진행률 바로 처리 상황 확인
4. 완료 시 "3D 마스크 다운로드" 링크 활성화

## 🔌 API 엔드포인트

### 작업 관리
- `POST /api/v1/jobs` - 새 작업 생성 (NIfTI 파일 업로드)
- `GET /api/v1/jobs/{job_id}/status` - 작업 상태 조회
- `GET /api/v1/jobs/{job_id}/result` - 결과 파일 다운로드

### 분할 작업
- `POST /api/v1/jobs/{job_id}/segment-2d` - 2D 분할 실행
- `POST /api/v1/jobs/{job_id}/propagate` - 3D Propagation 실행

## 🐳 Docker 사용

### 백엔드 컨테이너 실행
```bash
cd medsam_api_server
docker build -t medsam-api .
docker run -p 8000:8000 -v $(pwd)/../data:/app/data medsam-api
```

## 🔍 문제 해결

### 서비스가 시작되지 않는 경우
```bash
# 로그 확인
tail -f /tmp/api.log      # FastAPI 로그
tail -f /tmp/celery.log   # Celery 로그
tail -f /tmp/gradio.log   # Gradio 로그

# 포트 사용 확인
netstat -tlnp | grep -E ':(6379|8000|7860)'

# 프로세스 강제 종료
./scripts/stop.sh
```

### Redis 연결 오류
```bash
# Redis 상태 확인
redis-cli ping

# Redis 재시작
sudo systemctl restart redis
```

### Gradio 접속 불가
- `share=True` 옵션이 활성화되어 있어 공개 링크가 생성됩니다
- 로컬 접속이 안 되면 터미널에 표시되는 공개 URL 사용

## 📝 개발자 정보

- **프론트엔드**: Gradio 4.44.1
- **백엔드**: FastAPI, Celery, Redis
- **의료영상 처리**: Nibabel, NumPy
- **Python 버전**: 3.10+

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

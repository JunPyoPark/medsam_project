# 🚀 MedSAM2 HITL 빠른 시작 가이드

## 📋 서비스 관리 명령어

### 기본 명령어
```bash
# 모든 서비스 시작
./scripts/start.sh

# 모든 서비스 중지
./scripts/stop.sh

# 모든 서비스 재시작
./scripts/restart.sh

# 서비스 상태 확인
./scripts/status.sh

# 로그 확인
./scripts/logs.sh
```

### 개별 서비스 관리
```bash
# 특정 서비스만 시작
./scripts/start.sh redis    # Redis만
./scripts/start.sh api      # FastAPI만
./scripts/start.sh celery   # Celery만
./scripts/start.sh gradio   # Gradio만

# 특정 서비스만 중지
./scripts/stop.sh api       # FastAPI만
./scripts/stop.sh celery    # Celery만
./scripts/stop.sh gradio    # Gradio만

# 특정 서비스만 재시작
./scripts/restart.sh api    # FastAPI만
./scripts/restart.sh celery # Celery만
./scripts/restart.sh gradio # Gradio만
```

### 로그 확인
```bash
# 모든 로그 (최근 50줄)
./scripts/logs.sh

# 특정 서비스 로그
./scripts/logs.sh api       # FastAPI 로그
./scripts/logs.sh celery    # Celery 로그
./scripts/logs.sh gradio    # Gradio 로그

# 더 많은 로그 보기 (100줄)
./scripts/logs.sh all 100

# 실시간 로그 확인
tail -f /tmp/api.log        # FastAPI
tail -f /tmp/celery.log     # Celery
tail -f /tmp/gradio.log     # Gradio
```

## 🌐 접속 URL

- **Gradio UI**: http://127.0.0.1:7860
- **API 서버**: http://127.0.0.1:8000
- **API 문서**: http://127.0.0.1:8000/docs

## 🔧 사용법

### 1. 서비스 시작
```bash
cd /home/junpyo/projects/medsam_project
./scripts/start.sh
```

### 2. 웹 접속
브라우저에서 http://127.0.0.1:7860 접속

### 3. NIfTI 파일 업로드
1. "NIfTI (.nii.gz) 업로드"에서 파일 선택
2. "새 작업 시작" 버튼 클릭

### 4. 2D 분할
1. 슬라이더로 원하는 슬라이스로 이동
2. x1, y1, x2, y2 좌표 입력 (기본값: 200, 265, 240, 310)
3. "중간 슬라이스 2D 분할" 버튼 클릭
4. 자동으로 완료까지 대기

### 5. 3D Propagation
1. "3D Propagation 실행" 버튼 클릭
2. 진행률 바로 처리 상황 확인
3. 완료 시 다운로드 링크 활성화

## 🚨 문제 해결

### 서비스가 시작되지 않는 경우
```bash
# 상태 확인
./scripts/status.sh

# 로그 확인
./scripts/logs.sh

# 강제 재시작
./scripts/stop.sh
./scripts/start.sh
```

### 포트 충돌 시
```bash
# 포트 사용 확인
netstat -tlnp | grep -E ':(6379|8000|7860)'

# 프로세스 강제 종료
sudo kill -9 $(pgrep -f uvicorn)
sudo kill -9 $(pgrep -f celery)
sudo kill -9 $(pgrep -f gradio)
```

### Redis 연결 오류
```bash
# Redis 상태 확인
redis-cli ping

# Redis 재시작
sudo systemctl restart redis
```

## 📝 개발자 팁

### 코드 수정 후 재시작
```bash
# 프론트엔드 수정 후
./scripts/restart.sh gradio

# 백엔드 수정 후
./scripts/restart.sh api
./scripts/restart.sh celery
```

### 디버깅
```bash
# 실시간 로그 모니터링
./scripts/logs.sh all 100 | grep -i error

# 특정 서비스만 모니터링
tail -f /tmp/api.log | grep -i error
```

### 서비스 완전 정리
```bash
# 모든 서비스 중지
./scripts/stop.sh

# 로그 파일 정리
rm -f /tmp/api.log /tmp/celery.log /tmp/gradio.log

# 데이터 정리 (주의!)
rm -rf data/*
```

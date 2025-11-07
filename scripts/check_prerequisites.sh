#!/bin/bash

# 시스템 의존성 확인 스크립트
# 새 서버에서 Docker 배포 전 필수 요구사항 확인

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "시스템 의존성 확인 시작"
echo "=========================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERROR_COUNT=0
WARNING_COUNT=0

# 체크 함수
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ERROR_COUNT=$((ERROR_COUNT + 1))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    WARNING_COUNT=$((WARNING_COUNT + 1))
}

# 1. Docker 설치 확인
echo "1. Docker 설치 확인..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    check_pass "Docker 설치됨: $DOCKER_VERSION"
    
    # Docker 서비스 실행 확인
    if systemctl is-active --quiet docker; then
        check_pass "Docker 서비스 실행 중"
    else
        check_fail "Docker 서비스가 실행되지 않음"
    fi
else
    check_fail "Docker가 설치되지 않음"
fi

# 2. Docker Compose 확인
echo ""
echo "2. Docker Compose 확인..."
if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
    if docker compose version &> /dev/null; then
        COMPOSE_VERSION=$(docker compose version)
        check_pass "Docker Compose 설치됨: $COMPOSE_VERSION"
    else
        COMPOSE_VERSION=$(docker-compose --version)
        check_pass "Docker Compose 설치됨: $COMPOSE_VERSION"
    fi
else
    check_fail "Docker Compose가 설치되지 않음"
fi

# 3. NVIDIA 드라이버 확인
echo ""
echo "3. NVIDIA 드라이버 확인..."
if command -v nvidia-smi &> /dev/null; then
    DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
    check_pass "NVIDIA 드라이버 설치됨: $DRIVER_VERSION"
    
    # GPU 개수 확인
    GPU_COUNT=$(nvidia-smi -L | wc -l)
    check_pass "GPU 개수: $GPU_COUNT"
else
    check_warn "nvidia-smi를 찾을 수 없음 (GPU 사용 시 필요)"
fi

# 4. MIG 디바이스 확인
echo ""
echo "4. MIG 디바이스 확인..."
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi -L | grep -q "MIG"; then
        check_pass "MIG 모드 활성화됨"
        echo "  MIG 디바이스 목록:"
        nvidia-smi -L | grep "MIG" | while read line; do
            echo "    $line"
        done
    else
        check_warn "MIG 모드가 활성화되지 않음"
    fi
else
    check_warn "nvidia-smi를 사용할 수 없어 MIG 확인 불가"
fi

# 5. NVIDIA Container Toolkit 확인
echo ""
echo "5. NVIDIA Container Toolkit 확인..."
if [ -f /usr/bin/nvidia-container-runtime ] || [ -f /usr/bin/nvidia-container-toolkit ]; then
    check_pass "NVIDIA Container Toolkit 설치됨"
else
    check_warn "NVIDIA Container Toolkit이 설치되지 않음 (GPU 사용 시 필요)"
fi

# 6. Docker GPU 접근 테스트
echo ""
echo "6. Docker GPU 접근 테스트..."
if command -v nvidia-smi &> /dev/null; then
    if docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi &> /dev/null; then
        check_pass "Docker에서 GPU 접근 가능"
    else
        check_fail "Docker에서 GPU 접근 불가"
    fi
else
    check_warn "nvidia-smi가 없어 GPU 접근 테스트 불가"
fi

# 7. MedSAM2 저장소 확인
echo ""
echo "7. MedSAM2 저장소 확인..."
if [ -d "$PROJECT_ROOT/MedSAM2" ]; then
    if [ -f "$PROJECT_ROOT/MedSAM2/setup.py" ]; then
        check_pass "MedSAM2 저장소 존재함"
    else
        check_fail "MedSAM2 디렉토리는 있지만 setup.py가 없음"
    fi
else
    check_fail "MedSAM2 저장소가 없음 (필요: git clone https://github.com/bowang-lab/MedSAM2.git)"
fi

# 8. 모델 파일 확인
echo ""
echo "8. 모델 파일 확인..."
MODEL_FILE="$PROJECT_ROOT/models/MedSAM2_latest.pt"
if [ -f "$MODEL_FILE" ]; then
    MODEL_SIZE=$(ls -lh "$MODEL_FILE" | awk '{print $5}')
    check_pass "모델 파일 존재함: $MODEL_SIZE"
    
    # 파일 크기 확인 (약 149MB)
    FILE_SIZE=$(stat -f%z "$MODEL_FILE" 2>/dev/null || stat -c%s "$MODEL_FILE" 2>/dev/null)
    if [ "$FILE_SIZE" -gt 100000000 ]; then  # 100MB 이상
        check_pass "모델 파일 크기 정상"
    else
        check_warn "모델 파일 크기가 비정상적으로 작음"
    fi
else
    check_fail "모델 파일이 없음: $MODEL_FILE"
fi

# 9. 필수 디렉토리 확인
echo ""
echo "9. 필수 디렉토리 확인..."
for dir in data temp models; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
        check_pass "디렉토리 존재: $dir"
    else
        check_warn "디렉토리 없음: $dir (자동 생성됨)"
        mkdir -p "$PROJECT_ROOT/$dir"
    fi
done

# 10. 포트 사용 가능 여부 확인
echo ""
echo "10. 포트 사용 가능 여부 확인..."
PORTS=(8000 5556 6380)
for port in "${PORTS[@]}"; do
    if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
        check_warn "포트 $port가 이미 사용 중"
    else
        check_pass "포트 $port 사용 가능"
    fi
done

# 결과 요약
echo ""
echo "=========================================="
echo "확인 완료"
echo "=========================================="
echo ""

if [ $ERROR_COUNT -eq 0 ] && [ $WARNING_COUNT -eq 0 ]; then
    echo -e "${GREEN}모든 확인 항목 통과!${NC}"
    exit 0
elif [ $ERROR_COUNT -eq 0 ]; then
    echo -e "${YELLOW}경고: $WARNING_COUNT개${NC}"
    echo "대부분의 경우 정상 작동하지만 일부 기능이 제한될 수 있습니다."
    exit 0
else
    echo -e "${RED}오류: $ERROR_COUNT개${NC}"
    echo -e "${YELLOW}경고: $WARNING_COUNT개${NC}"
    echo ""
    echo "오류를 해결한 후 다시 실행하세요."
    exit 1
fi


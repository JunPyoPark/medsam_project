#!/bin/bash

# 빠른 시작 스크립트
# 새 서버에서 처음 실행 시 모든 설정을 자동으로 완료하고 서비스를 시작

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  MedSAM2 프로젝트 빠른 시작${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. 사전 요구사항 확인
echo -e "${YELLOW}[1/6] 사전 요구사항 확인 중...${NC}"
if ! "$SCRIPT_DIR/check_prerequisites.sh"; then
    echo -e "${RED}❌ 사전 요구사항 확인 실패${NC}"
    echo "필수 항목을 설치한 후 다시 시도하세요."
    exit 1
fi
echo ""

# 2. MedSAM2 저장소 확인 및 클론
echo -e "${YELLOW}[2/6] MedSAM2 저장소 확인 중...${NC}"
if [ ! -d "$PROJECT_ROOT/MedSAM2" ]; then
    echo -e "${BLUE}MedSAM2 저장소 클론 중...${NC}"
    cd "$PROJECT_ROOT"
    git clone https://github.com/bowang-lab/MedSAM2.git || {
        echo -e "${RED}❌ MedSAM2 클론 실패${NC}"
        exit 1
    }
    echo -e "${GREEN}✅ MedSAM2 저장소 클론 완료${NC}"
else
    if [ -f "$PROJECT_ROOT/MedSAM2/setup.py" ]; then
        echo -e "${GREEN}✅ MedSAM2 저장소 이미 존재함${NC}"
    else
        echo -e "${RED}❌ MedSAM2 디렉토리는 있지만 setup.py가 없음${NC}"
        exit 1
    fi
fi
echo ""

# 3. 필수 디렉토리 생성
echo -e "${YELLOW}[3/6] 필수 디렉토리 생성 중...${NC}"
mkdir -p "$PROJECT_ROOT/data" "$PROJECT_ROOT/temp" "$PROJECT_ROOT/models"
echo -e "${GREEN}✅ 디렉토리 생성 완료${NC}"
echo ""

# 4. 모델 파일 확인 및 다운로드
echo -e "${YELLOW}[4/6] 모델 파일 확인 중...${NC}"
MODEL_FILE="$PROJECT_ROOT/models/MedSAM2_latest.pt"
if [ ! -f "$MODEL_FILE" ] || [ ! -s "$MODEL_FILE" ]; then
    echo -e "${BLUE}모델 파일 다운로드 중... (약 149MB)${NC}"
    if [ -f "$SCRIPT_DIR/download_models.sh" ]; then
        chmod +x "$SCRIPT_DIR/download_models.sh"
        "$SCRIPT_DIR/download_models.sh" || {
            echo -e "${RED}❌ 모델 다운로드 실패${NC}"
            exit 1
        }
    else
        echo -e "${RED}❌ download_models.sh 스크립트를 찾을 수 없음${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ 모델 파일 다운로드 완료${NC}"
else
    MODEL_SIZE=$(ls -lh "$MODEL_FILE" | awk '{print $5}')
    echo -e "${GREEN}✅ 모델 파일 이미 존재함 ($MODEL_SIZE)${NC}"
fi
echo ""

# 5. Docker Compose 빌드 및 실행
echo -e "${YELLOW}[5/6] Docker Compose 빌드 및 실행 중...${NC}"
cd "$PROJECT_ROOT"

# 기존 컨테이너 중지 (있는 경우)
if docker compose ps | grep -q "Up"; then
    echo -e "${YELLOW}기존 컨테이너 중지 중...${NC}"
    docker compose down
fi

# 빌드 및 실행
echo -e "${BLUE}Docker 이미지 빌드 중... (10-20분 소요될 수 있습니다)${NC}"
if docker compose up --build -d; then
    echo -e "${GREEN}✅ Docker 빌드 및 실행 완료${NC}"
    
    # 서비스 시작 대기
    echo -e "${YELLOW}서비스 초기화 대기 중...${NC}"
    sleep 15
    
    # 상태 확인
    echo -e "${BLUE}서비스 상태 확인 중...${NC}"
    docker compose ps
    
    # API 서버 헬스체크
    echo -e "${YELLOW}API 서버 헬스체크 중...${NC}"
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ API 서버 응답 확인됨${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}❌ API 서버 응답 실패 (30초 타임아웃)${NC}"
            echo "로그 확인: docker compose logs api"
        else
            echo -e "${YELLOW}  대기 중... ($i/30)${NC}"
            sleep 1
        fi
    done
else
    echo -e "${RED}❌ Docker 빌드 또는 실행 실패${NC}"
    echo "로그 확인: docker compose logs"
    exit 1
fi
echo ""

# 6. 최종 상태 확인
echo -e "${YELLOW}[6/6] 최종 상태 확인 중...${NC}"
echo ""

# 컨테이너 상태
echo -e "${BLUE}컨테이너 상태:${NC}"
docker compose ps
echo ""

# GPU 접근 확인
if command -v nvidia-smi &> /dev/null; then
    echo -e "${BLUE}Worker GPU 접근 확인:${NC}"
    if docker compose exec -T worker1 nvidia-smi -L 2>/dev/null | head -1; then
        echo -e "${GREEN}✅ Worker1 GPU 접근 가능${NC}"
    else
        echo -e "${YELLOW}⚠ Worker1 GPU 접근 확인 실패 (MIG 설정 확인 필요)${NC}"
    fi
    echo ""
fi

# 완료 메시지
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  빠른 시작 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}🌐 접속 URL:${NC}"
echo "  - API 서버: http://127.0.0.1:8000"
echo "  - API 문서: http://127.0.0.1:8000/docs"
echo "  - Health Check: http://127.0.0.1:8000/health"
echo "  - Flower (Celery 모니터): http://127.0.0.1:5556"
echo ""
echo -e "${BLUE}📊 유용한 명령어:${NC}"
echo "  - 서비스 상태: docker compose ps"
echo "  - 로그 확인: docker compose logs -f"
echo "  - 특정 서비스 로그: docker compose logs -f worker1"
echo "  - 서비스 중지: docker compose down"
echo "  - 서비스 재시작: docker compose restart"
echo ""
echo -e "${YELLOW}⚠ 참고:${NC}"
echo "  - Gradio 프론트엔드는 별도로 실행해야 합니다:"
echo "    cd medsam_gradio_viewer && python app.py"
echo "  - 또는 ./scripts/start.sh gradio"
echo ""


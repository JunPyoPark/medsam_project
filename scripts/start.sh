#!/bin/bash
set -euo pipefail

# 🚀 MedSAM2 HITL 서비스 시작 스크립트
# 현재 구조: Docker(Backend) + Local(Frontend)

# 스크립트 위치 기준으로 프로젝트 루트 자동 탐지
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv/bin/activate"
PID_DIR="$PROJECT_ROOT/.pids"
LOG_GRADIO="/tmp/gradio.log"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 MedSAM2 HITL 서비스 시작 중...${NC}"

mkdir -p "$PID_DIR"
cd "$PROJECT_ROOT"

# 가상환경 활성화
if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
    echo -e "${GREEN}✅ 가상환경 활성화됨${NC}"
fi

# 특정 서비스만 시작하는 함수들
start_backend() {
    echo -e "${YELLOW}📋 Docker 백엔드 서비스 시작 중...${NC}"
    
    if docker compose ps | grep -q "Up"; then
        echo -e "${GREEN}✅ Docker 서비스가 이미 실행 중입니다${NC}"
        docker compose ps
    else
        echo -e "${BLUE}🐳 Docker Compose 시작 중...${NC}"
        docker compose up -d
        
        # 서비스 시작 대기
        echo -e "${YELLOW}⏳ 서비스 초기화 대기 중...${NC}"
        sleep 10
        
        # 상태 확인
        if docker compose ps | grep -q "Up"; then
            echo -e "${GREEN}✅ Docker 백엔드 서비스 시작 완료${NC}"
            docker compose ps
        else
            echo -e "${RED}❌ Docker 서비스 시작 실패${NC}"
            docker compose logs --tail=20
            return 1
        fi
    fi
}

start_gradio() {
    echo -e "${YELLOW}🎨 Gradio 프론트엔드 시작 중...${NC}"
    
    # 기존 Gradio 프로세스 확인
    if [ -f "$PID_DIR/gradio.pid" ] && kill -0 "$(cat $PID_DIR/gradio.pid)" 2>/dev/null; then
        echo -e "${GREEN}✅ Gradio가 이미 실행 중입니다 (PID: $(cat $PID_DIR/gradio.pid))${NC}"
        return 0
    fi
    
    # 기존 프로세스 정리
    pkill -f "python.*app.py" 2>/dev/null || true
    pkill -f "gradio" 2>/dev/null || true
    sleep 2
    
    # Gradio 시작 (unbuffered 출력으로 실시간 로그)
    cd "$PROJECT_ROOT/medsam_gradio_viewer"
    nohup python -u app.py > "$LOG_GRADIO" 2>&1 &
    GRADIO_PID=$!
    echo $GRADIO_PID > "$PID_DIR/gradio.pid"
    
    # 시작 확인
    sleep 5
    if kill -0 "$GRADIO_PID" 2>/dev/null; then
        echo -e "${GREEN}✅ Gradio 시작됨 (PID: $GRADIO_PID)${NC}"
        
        # 접속 확인 (최대 30초 대기)
        for i in {1..10}; do
            if curl -s http://localhost:7860 > /dev/null 2>&1; then
                echo -e "${GREEN}✅ Gradio 서비스 응답 확인됨${NC}"
                break
            fi
            echo -e "${YELLOW}⏳ Gradio 서비스 응답 대기 중... ($i/10)${NC}"
            sleep 3
        done
    else
        echo -e "${RED}❌ Gradio 시작 실패${NC}"
        return 1
    fi
}

# 인수에 따른 선택적 시작
case "${1:-all}" in
    "backend"|"docker")
        start_backend
        ;;
    "frontend"|"gradio")
        start_gradio
        ;;
    "all"|*)
        start_backend
        start_gradio
        ;;
esac

echo ""
echo -e "${GREEN}🎉 서비스 시작 완료!${NC}"
echo ""
echo -e "${BLUE}🌐 접속 URL:${NC}"
echo "  - Gradio UI: http://127.0.0.1:7860"
echo "  - API 서버: http://127.0.0.1:8000"
echo "  - API 문서: http://127.0.0.1:8000/docs"
echo ""
echo -e "${BLUE}📊 서비스 상태 확인:${NC}"
echo "  - 전체 상태: ./scripts/status.sh"
echo "  - Docker 로그: docker compose logs -f"
echo "  - Gradio 로그: tail -f $LOG_GRADIO"
echo ""
echo -e "${BLUE}💡 사용법:${NC}"
echo "  - 전체 시작: ./scripts/start.sh"
echo "  - 백엔드만: ./scripts/start.sh backend"
echo "  - 프론트엔드만: ./scripts/start.sh gradio" 
#!/bin/bash
set -euo pipefail

# 🛑 MedSAM2 HITL 서비스 중지 스크립트
# 현재 구조: Docker(Backend) + Local(Frontend)

# 스크립트 위치 기준으로 프로젝트 루트 자동 탐지
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_DIR="$PROJECT_ROOT/.pids"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 MedSAM2 HITL 서비스 중지 중...${NC}"

cd "$PROJECT_ROOT"

# Docker 백엔드 서비스 중지
stop_backend() {
    echo -e "${YELLOW}📋 Docker 백엔드 서비스 중지 중...${NC}"
    
    if docker compose ps | grep -q "Up"; then
        docker compose down
        echo -e "${GREEN}✅ Docker 백엔드 서비스 중지됨${NC}"
    else
        echo -e "${YELLOW}⚠️  Docker 서비스가 실행 중이 아닙니다${NC}"
    fi
}

# Gradio 프론트엔드 중지
stop_gradio() {
    echo -e "${YELLOW}🎨 Gradio 프론트엔드 중지 중...${NC}"
    
    # PID 파일로 중지
    if [ -f "$PID_DIR/gradio.pid" ]; then
        local pid
        pid=$(cat "$PID_DIR/gradio.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
            echo -e "${GREEN}✅ Gradio 중지됨 (PID: $pid)${NC}"
        else
            echo -e "${YELLOW}⚠️  Gradio PID 파일에 있는 프로세스가 실행 중이 아닙니다${NC}"
        fi
        rm -f "$PID_DIR/gradio.pid"
    fi
    
    # 관련 프로세스 모두 정리
    echo -e "${YELLOW}🧹 Gradio 관련 프로세스 정리 중...${NC}"
    pkill -f "python.*app.py" 2>/dev/null || true
    pkill -f "gradio" 2>/dev/null || true
    pkill -f "frpc" 2>/dev/null || true  # Gradio tunnel 프로세스
    
    # 잠시 대기 후 확인
    sleep 2
    if pgrep -f "python.*app.py" > /dev/null || pgrep -f "gradio" > /dev/null; then
        echo -e "${YELLOW}⚠️  일부 Gradio 프로세스가 여전히 실행 중일 수 있습니다${NC}"
        echo -e "${BLUE}💡 강제 종료: pkill -9 -f gradio${NC}"
    else
        echo -e "${GREEN}✅ 모든 Gradio 프로세스 정리 완료${NC}"
    fi
}

# 모든 관련 프로세스 정리
cleanup_all() {
    echo -e "${YELLOW}🧹 추가 정리 작업...${NC}"
    
    # 로그 tail 프로세스 정리
    pkill -f "tail.*log" 2>/dev/null || true
    
    # PID 디렉토리 정리
    if [ -d "$PID_DIR" ]; then
        rm -rf "$PID_DIR"
        echo -e "${GREEN}✅ PID 파일들 정리됨${NC}"
    fi
    
    echo -e "${GREEN}✅ 정리 작업 완료${NC}"
}

# 인수에 따른 선택적 중지
case "${1:-all}" in
    "backend"|"docker")
        stop_backend
        ;;
    "frontend"|"gradio")
        stop_gradio
        ;;
    "all"|*)
        stop_backend
        stop_gradio
        cleanup_all
        ;;
esac

echo ""
echo -e "${GREEN}🎉 서비스 중지 완료!${NC}"
echo ""
echo -e "${BLUE}💡 사용법:${NC}"
echo "  - 전체 중지: ./scripts/stop.sh"
echo "  - 백엔드만: ./scripts/stop.sh backend"
echo "  - 프론트엔드만: ./scripts/stop.sh gradio"
echo "  - 상태 확인: ./scripts/status.sh" 
#!/bin/bash
set -euo pipefail

# 📊 MedSAM2 HITL 서비스 상태 확인 스크립트
# 현재 구조: Docker(Backend) + Local(Frontend)

# 스크립트 위치 기준으로 프로젝트 루트 자동 탐지
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}📊 MedSAM2 HITL 서비스 상태 확인${NC}"
echo "=================================="

cd "$PROJECT_ROOT"

# Docker 백엔드 서비스 상태
echo -e "${PURPLE}🐳 Docker 백엔드 서비스:${NC}"
if command -v docker > /dev/null 2>&1; then
    if docker compose ps 2>/dev/null | grep -q "Up"; then
        echo -e "${GREEN}✅ Docker 서비스 실행 중${NC}"
        docker compose ps | grep -E "(NAME|Up|Exited)" | head -10
        echo ""
        
        # 개별 서비스 상태
        echo -e "${CYAN}🔴 Redis:${NC}"
        if docker compose ps redis 2>/dev/null | grep -q "Up"; then
            echo -e "  ${GREEN}✅ 실행 중 (Docker)${NC}"
            if docker compose exec redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
                echo -e "  ${GREEN}✅ 연결 가능${NC}"
            else
                echo -e "  ${YELLOW}⚠️  연결 확인 실패${NC}"
            fi
        else
            echo -e "  ${RED}❌ 중지됨${NC}"
        fi
        
        echo -e "${CYAN}🚀 FastAPI:${NC}"
        if docker compose ps api 2>/dev/null | grep -q "Up"; then
            echo -e "  ${GREEN}✅ 실행 중 (Docker)${NC}"
            if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
                echo -e "  ${GREEN}✅ 응답 가능 (http://127.0.0.1:8000)${NC}"
            else
                echo -e "  ${YELLOW}⚠️  응답 확인 실패${NC}"
            fi
        else
            echo -e "  ${RED}❌ 중지됨${NC}"
        fi
        
        echo -e "${CYAN}⚙️  Celery Worker:${NC}"
        if docker compose ps worker 2>/dev/null | grep -q "Up"; then
            echo -e "  ${GREEN}✅ 실행 중 (Docker)${NC}"
        else
            echo -e "  ${RED}❌ 중지됨${NC}"
        fi
        
        echo -e "${CYAN}📊 Celery Monitor:${NC}"
        if docker compose ps monitor 2>/dev/null | grep -q "Up"; then
            echo -e "  ${GREEN}✅ 실행 중 (Docker)${NC}"
            echo -e "  ${BLUE}💡 모니터링: http://127.0.0.1:5556${NC}"
        else
            echo -e "  ${RED}❌ 중지됨${NC}"
        fi
        
    else
        echo -e "${RED}❌ Docker 서비스 중지됨${NC}"
        if docker compose ps 2>/dev/null | grep -q "Exit"; then
            echo -e "${YELLOW}⚠️  일부 서비스가 종료 상태입니다:${NC}"
            docker compose ps | grep "Exit"
        fi
    fi
else
    echo -e "${RED}❌ docker 명령을 찾을 수 없습니다${NC}"
fi

echo ""

# Gradio 프론트엔드 상태
echo -e "${PURPLE}🎨 Gradio 프론트엔드:${NC}"
GRADIO_RUNNING=false

# PID 파일 확인
if [ -f "$PROJECT_ROOT/.pids/gradio.pid" ]; then
    GRADIO_PID=$(cat "$PROJECT_ROOT/.pids/gradio.pid")
    if kill -0 "$GRADIO_PID" 2>/dev/null; then
        echo -e "  ${GREEN}✅ 실행 중 (PID: $GRADIO_PID)${NC}"
        GRADIO_RUNNING=true
    else
        echo -e "  ${YELLOW}⚠️  PID 파일은 있지만 프로세스가 실행되지 않음${NC}"
    fi
fi

# 프로세스 직접 확인
if ! $GRADIO_RUNNING; then
    if pgrep -f "python.*app.py" > /dev/null; then
        GRADIO_PIDS=$(pgrep -f "python.*app.py")
        echo -e "  ${GREEN}✅ 실행 중 (PID: $GRADIO_PIDS)${NC}"
        GRADIO_RUNNING=true
    else
        echo -e "  ${RED}❌ 중지됨${NC}"
    fi
fi

# 접속 확인
if $GRADIO_RUNNING; then
    if curl -s http://127.0.0.1:7860/ > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ 응답 가능 (http://127.0.0.1:7860)${NC}"
    else
        echo -e "  ${YELLOW}⚠️  응답 확인 실패${NC}"
    fi
fi

echo ""

# 포트 사용 현황
echo -e "${PURPLE}🔌 포트 사용 현황:${NC}"
PORT_OUTPUT=$(netstat -tlnp 2>/dev/null | grep -E ':(6380|8000|7860|5556)' || echo "")
if [ -n "$PORT_OUTPUT" ]; then
    echo "$PORT_OUTPUT" | while read -r line; do
        if echo "$line" | grep -q ":6380"; then
            echo -e "  ${CYAN}Redis (6380):${NC} $line"
        elif echo "$line" | grep -q ":8000"; then
            echo -e "  ${CYAN}API (8000):${NC} $line"
        elif echo "$line" | grep -q ":7860"; then
            echo -e "  ${CYAN}Gradio (7860):${NC} $line"
        elif echo "$line" | grep -q ":5556"; then
            echo -e "  ${CYAN}Monitor (5556):${NC} $line"
        fi
    done
else
    echo -e "  ${YELLOW}⚠️  주요 포트에서 실행 중인 서비스 없음${NC}"
fi

echo ""

# 로그 파일 상태
echo -e "${PURPLE}📝 로그 파일 상태:${NC}"

# Docker 로그 (최근 에러 확인)
echo -e "  ${CYAN}Docker 로그:${NC}"
if docker compose ps 2>/dev/null | grep -q "Up"; then
    ERROR_COUNT=$(docker compose logs --tail=100 2>/dev/null | grep -i error | wc -l 2>/dev/null || echo "0")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "    ${YELLOW}⚠️  최근 에러 $ERROR_COUNT 개 발견${NC}"
        echo -e "    ${BLUE}💡 확인: docker compose logs --tail=50${NC}"
    else
        echo -e "    ${GREEN}✅ 최근 에러 없음${NC}"
    fi
else
    echo -e "    ${RED}❌ Docker 서비스 중지됨${NC}"
fi

# Gradio 로그
GRADIO_LOG="/tmp/gradio.log"
echo -e "  ${CYAN}Gradio 로그:${NC}"
if [ -f "$GRADIO_LOG" ]; then
    LOG_SIZE=$(du -h "$GRADIO_LOG" | cut -f1)
    RECENT_ERRORS=$(tail -100 "$GRADIO_LOG" 2>/dev/null | grep -i -E "(error|exception|failed)" | wc -l || echo "0")
    echo -e "    ${GREEN}✅ 파일 존재 ($LOG_SIZE)${NC}"
    if [ "$RECENT_ERRORS" -gt 0 ]; then
        echo -e "    ${YELLOW}⚠️  최근 에러 $RECENT_ERRORS 개 발견${NC}"
        echo -e "    ${BLUE}💡 확인: tail -50 $GRADIO_LOG${NC}"
    else
        echo -e "    ${GREEN}✅ 최근 에러 없음${NC}"
    fi
else
    echo -e "    ${YELLOW}⚠️  로그 파일 없음${NC}"
fi

echo ""

# 도움말
echo -e "${PURPLE}💡 도움말:${NC}"
echo -e "  ${BLUE}서비스 관리:${NC}"
echo "    - 전체 시작: ./scripts/start.sh"
echo "    - 전체 중지: ./scripts/stop.sh"
echo "    - 재시작: ./scripts/restart.sh"
echo ""
echo -e "  ${BLUE}개별 관리:${NC}"
echo "    - 백엔드만: ./scripts/start.sh backend"
echo "    - 프론트엔드만: ./scripts/start.sh gradio"
echo ""
echo -e "  ${BLUE}로그 확인:${NC}"
echo "    - Docker 로그: docker compose logs -f"
echo "    - Gradio 로그: tail -f $GRADIO_LOG"
echo ""
echo -e "  ${BLUE}접속 URL:${NC}"
echo "    - Gradio UI: http://127.0.0.1:7860"
echo "    - API 서버: http://127.0.0.1:8000"
echo "    - API 문서: http://127.0.0.1:8000/docs"
echo "    - Celery 모니터: http://127.0.0.1:5556"

#!/bin/bash
set -euo pipefail

# 🔄 MedSAM2 HITL 서비스 재시작 스크립트
# 현재 구조: Docker(Backend) + Local(Frontend)

PROJECT_ROOT="/home/junpyo/projects/medsam_project"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 MedSAM2 HITL 서비스 재시작 중...${NC}"

cd "$PROJECT_ROOT"

# 인수에 따른 선택적 재시작
case "${1:-all}" in
    "backend"|"docker")
        echo -e "${YELLOW}📋 Docker 백엔드 서비스 재시작 중...${NC}"
        ./scripts/stop.sh backend
        sleep 3
        ./scripts/start.sh backend
        ;;
    "frontend"|"gradio")
        echo -e "${YELLOW}🎨 Gradio 프론트엔드 재시작 중...${NC}"
        ./scripts/stop.sh gradio
        sleep 2
        ./scripts/start.sh gradio
        ;;
    "all"|*)
        echo -e "${YELLOW}🔄 전체 서비스 재시작 중...${NC}"
        ./scripts/stop.sh all
        sleep 5
        ./scripts/start.sh all
        ;;
esac

echo ""
echo -e "${GREEN}🎉 서비스 재시작 완료!${NC}"
echo ""
echo -e "${BLUE}📊 상태 확인: ./scripts/status.sh${NC}"

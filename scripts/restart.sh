#!/bin/bash
set -euo pipefail

# MedSAM2 HITL 서비스 재시작 스크립트
# 사용법: ./scripts/restart.sh [서비스명]
# 서비스명: all, redis, api, celery, gradio

PROJECT_ROOT="/home/junpyo/projects/medsam_project"
SCRIPT_DIR="$PROJECT_ROOT/scripts"

echo "🔄 MedSAM2 HITL 서비스 재시작 중..."

# 서비스명 확인
SERVICE=${1:-all}

case $SERVICE in
    all)
        echo "📋 모든 서비스 재시작..."
        $SCRIPT_DIR/stop.sh
        sleep 2
        $SCRIPT_DIR/start.sh
        ;;
    redis)
        echo "📋 Redis 재시작..."
        $SCRIPT_DIR/stop.sh redis
        sleep 1
        $SCRIPT_DIR/start.sh redis
        ;;
    api)
        echo "📋 FastAPI 재시작..."
        $SCRIPT_DIR/stop.sh api
        sleep 1
        $SCRIPT_DIR/start.sh api
        ;;
    celery)
        echo "📋 Celery 재시작..."
        $SCRIPT_DIR/stop.sh celery
        sleep 1
        $SCRIPT_DIR/start.sh celery
        ;;
    gradio)
        echo "📋 Gradio 재시작..."
        $SCRIPT_DIR/stop.sh gradio
        sleep 1
        $SCRIPT_DIR/start.sh gradio
        ;;
    *)
        echo "❌ 잘못된 서비스명: $SERVICE"
        echo "사용법: $0 [all|redis|api|celery|gradio]"
        exit 1
        ;;
esac

echo "✅ 재시작 완료!"
echo ""
echo "🌐 접속 URL:"
echo "  - Gradio UI: http://127.0.0.1:7860"
echo "  - API 서버: http://127.0.0.1:8000"
echo "  - API 문서: http://127.0.0.1:8000/docs"
echo ""
echo "📊 서비스 상태 확인:"
echo "  - 로그: tail -f /tmp/{api,celery,gradio}.log"
echo "  - 프로세스: ps aux | grep -E '(uvicorn|celery|gradio)'"

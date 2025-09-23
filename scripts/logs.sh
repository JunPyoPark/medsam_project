#!/bin/bash
set -euo pipefail

# MedSAM2 HITL 서비스 로그 확인 스크립트
# 사용법: ./scripts/logs.sh [서비스명] [라인수]
# 서비스명: all, api, celery, gradio
# 라인수: 기본값 50

SERVICE=${1:-all}
LINES=${2:-50}

echo "📝 MedSAM2 HITL 서비스 로그 확인 (최근 $LINES줄)"
echo "================================================"

case $SERVICE in
    all)
        echo "📋 모든 서비스 로그:"
        echo ""
        echo "🚀 FastAPI 로그:"
        echo "----------------------------------------"
        if [ -f /tmp/api.log ]; then
            tail -n $LINES /tmp/api.log
        else
            echo "로그 파일이 없습니다: /tmp/api.log"
        fi
        echo ""
        echo "⚙️  Celery 로그:"
        echo "----------------------------------------"
        if [ -f /tmp/celery.log ]; then
            tail -n $LINES /tmp/celery.log
        else
            echo "로그 파일이 없습니다: /tmp/celery.log"
        fi
        echo ""
        echo "🎨 Gradio 로그:"
        echo "----------------------------------------"
        if [ -f /tmp/gradio.log ]; then
            tail -n $LINES /tmp/gradio.log
        else
            echo "로그 파일이 없습니다: /tmp/gradio.log"
        fi
        ;;
    api)
        echo "🚀 FastAPI 로그:"
        echo "----------------------------------------"
        if [ -f /tmp/api.log ]; then
            tail -n $LINES /tmp/api.log
        else
            echo "로그 파일이 없습니다: /tmp/api.log"
        fi
        ;;
    celery)
        echo "⚙️  Celery 로그:"
        echo "----------------------------------------"
        if [ -f /tmp/celery.log ]; then
            tail -n $LINES /tmp/celery.log
        else
            echo "로그 파일이 없습니다: /tmp/celery.log"
        fi
        ;;
    gradio)
        echo "🎨 Gradio 로그:"
        echo "----------------------------------------"
        if [ -f /tmp/gradio.log ]; then
            tail -n $LINES /tmp/gradio.log
        else
            echo "로그 파일이 없습니다: /tmp/gradio.log"
        fi
        ;;
    *)
        echo "❌ 잘못된 서비스명: $SERVICE"
        echo "사용법: $0 [all|api|celery|gradio] [라인수]"
        exit 1
        ;;
esac

echo ""
echo "💡 실시간 로그 확인:"
echo "  - 전체: tail -f /tmp/{api,celery,gradio}.log"
echo "  - FastAPI: tail -f /tmp/api.log"
echo "  - Celery: tail -f /tmp/celery.log"
echo "  - Gradio: tail -f /tmp/gradio.log"

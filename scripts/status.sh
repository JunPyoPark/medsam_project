#!/bin/bash
set -euo pipefail

# MedSAM2 HITL 서비스 상태 확인 스크립트
# 사용법: ./scripts/status.sh

echo "📊 MedSAM2 HITL 서비스 상태 확인"
echo "=================================="

# Redis 상태
echo "🔴 Redis:"
if pgrep -f "redis-server" > /dev/null; then
    echo "  ✅ 실행 중 (PID: $(pgrep -f redis-server))"
    if command -v redis-cli > /dev/null; then
        if redis-cli ping > /dev/null 2>&1; then
            echo "  ✅ 연결 가능"
        else
            echo "  ❌ 연결 불가"
        fi
    fi
else
    echo "  ❌ 중지됨"
fi

# FastAPI 상태
echo ""
echo "🚀 FastAPI:"
if pgrep -f "uvicorn.*medsam_api_server" > /dev/null; then
    echo "  ✅ 실행 중 (PID: $(pgrep -f uvicorn))"
    if curl -s http://127.0.0.1:8000/ > /dev/null 2>&1; then
        echo "  ✅ 응답 가능 (http://127.0.0.1:8000)"
    else
        echo "  ❌ 응답 불가"
    fi
else
    echo "  ❌ 중지됨"
fi

# Celery 상태
echo ""
echo "⚙️  Celery Worker:"
if pgrep -f "celery.*worker" > /dev/null; then
    echo "  ✅ 실행 중 (PID: $(pgrep -f celery))"
else
    echo "  ❌ 중지됨"
fi

# Gradio 상태
echo ""
echo "🎨 Gradio:"
if pgrep -f "gradio" > /dev/null; then
    echo "  ✅ 실행 중 (PID: $(pgrep -f gradio))"
    if curl -s http://127.0.0.1:7860/ > /dev/null 2>&1; then
        echo "  ✅ 응답 가능 (http://127.0.0.1:7860)"
    else
        echo "  ❌ 응답 불가"
    fi
else
    echo "  ❌ 중지됨"
fi

# 포트 사용 현황
echo ""
echo "🔌 포트 사용 현황:"
netstat -tlnp 2>/dev/null | grep -E ':(6379|8000|7860)' || echo "  사용 중인 포트 없음"

# 로그 파일 크기
echo ""
echo "📝 로그 파일 크기:"
for log in /tmp/api.log /tmp/celery.log /tmp/gradio.log; do
    if [ -f "$log" ]; then
        size=$(du -h "$log" | cut -f1)
        echo "  $log: $size"
    else
        echo "  $log: 없음"
    fi
done

echo ""
echo "💡 도움말:"
echo "  - 서비스 시작: ./scripts/start.sh"
echo "  - 서비스 중지: ./scripts/stop.sh"
echo "  - 서비스 재시작: ./scripts/restart.sh"
echo "  - 로그 확인: tail -f /tmp/{api,celery,gradio}.log"

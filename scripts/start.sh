#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/home/junpyo/projects/medsam_project"
VENV_PATH="$PROJECT_ROOT/.venv/bin/activate"
PID_DIR="$PROJECT_ROOT/.pids"
LOG_API="/tmp/api.log"
LOG_CELERY="/tmp/celery.log"
LOG_GRADIO="/tmp/gradio.log"

mkdir -p "$PID_DIR"

if [ -f "$VENV_PATH" ]; then
  # shellcheck disable=SC1090
  source "$VENV_PATH"
fi

# 1) Start Redis if possible
start_redis() {
  if command -v redis-cli >/dev/null 2>&1; then
    if redis-cli ping >/dev/null 2>&1; then
      echo "[OK] Redis already running"
      return 0
    fi
  fi

  if command -v systemctl >/dev/null 2>&1; then
    if systemctl list-unit-files | grep -q redis; then
      sudo systemctl start redis || true
    fi
  elif command -v service >/dev/null 2>&1; then
    sudo service redis-server start || true
  fi

  if command -v redis-server >/dev/null 2>&1; then
    if ! redis-cli ping >/dev/null 2>&1; then
      redis-server --daemonize yes || true
    fi
  fi

  if command -v redis-cli >/dev/null 2>&1 && redis-cli ping >/dev/null 2>&1; then
    echo "[OK] Redis running"
  else
    echo "[WARN] Redis not running. Celery가 동작하지 않을 수 있습니다."
  fi
}

start_api() {
  if [ -f "$PID_DIR/api.pid" ] && kill -0 "$(cat $PID_DIR/api.pid)" >/dev/null 2>&1; then
    echo "[SKIP] API already running (PID $(cat $PID_DIR/api.pid))"
  else
    nohup uvicorn medsam_api_server.main:app --host 0.0.0.0 --port 8000 >"$LOG_API" 2>&1 &
    echo $! >"$PID_DIR/api.pid"
    echo "[OK] API started (PID $(cat $PID_DIR/api.pid))"
  fi
}

start_celery() {
  if [ -f "$PID_DIR/celery.pid" ] && kill -0 "$(cat $PID_DIR/celery.pid)" >/dev/null 2>&1; then
    echo "[SKIP] Celery already running (PID $(cat $PID_DIR/celery.pid))"
  else
    nohup celery -A medsam_api_server.celery_app.celery_app worker --loglevel=INFO >"$LOG_CELERY" 2>&1 &
    echo $! >"$PID_DIR/celery.pid"
    echo "[OK] Celery started (PID $(cat $PID_DIR/celery.pid))"
  fi
}

start_gradio() {
  if [ -f "$PID_DIR/gradio.pid" ] && kill -0 "$(cat $PID_DIR/gradio.pid)" >/dev/null 2>&1; then
    echo "[SKIP] Gradio already running (PID $(cat $PID_DIR/gradio.pid))"
  else
    nohup python "$PROJECT_ROOT/medsam_gradio_viewer/app.py" >"$LOG_GRADIO" 2>&1 &
    echo $! >"$PID_DIR/gradio.pid"
    echo "[OK] Gradio started (PID $(cat $PID_DIR/gradio.pid))"
  fi
}

start_redis
start_api
start_celery
start_gradio

echo "Logs:"
echo "  API    : $LOG_API"
echo "  Celery : $LOG_CELERY"
echo "  Gradio : $LOG_GRADIO" 
#!/bin/bash
set -euo pipefail

PROJECT_ROOT="/home/junpyo/projects/medsam_project"
PID_DIR="$PROJECT_ROOT/.pids"

stop_one() {
  local name="$1"
  local pid_file="$PID_DIR/${name}.pid"
  if [ -f "$pid_file" ]; then
    local pid
    pid=$(cat "$pid_file")
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" || true
      sleep 1
      if kill -0 "$pid" >/dev/null 2>&1; then
        kill -9 "$pid" || true
      fi
      echo "[OK] Stopped $name (PID $pid)"
    else
      echo "[SKIP] $name not running"
    fi
    rm -f "$pid_file"
  else
    echo "[SKIP] $name pid file not found"
  fi
}

stop_one api
stop_one celery
stop_one gradio

echo "Done." 
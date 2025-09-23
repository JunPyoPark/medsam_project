#!/bin/bash
set -euo pipefail
export C_FORCE_ROOT=1
exec celery -A medsam_api_server.celery_app.celery_app worker --loglevel=INFO 
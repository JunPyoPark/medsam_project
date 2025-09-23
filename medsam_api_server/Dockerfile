FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_ROOT=/app/data \
    CELERY_BROKER_URL=redis://redis:6379/0 \
    CELERY_RESULT_BACKEND=redis://redis:6379/1

WORKDIR /app

COPY medsam_api_server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY medsam_api_server /app/medsam_api_server
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "medsam_api_server.main:app", "--host", "0.0.0.0", "--port", "8000"]

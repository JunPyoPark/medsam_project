import os
from celery import Celery


def create_celery_app() -> Celery:
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    app = Celery(
        "medsam_api",
        broker=broker_url,
        backend=result_backend,
        include=[
            "medsam_api_server.tasks.segmentation",
        ],
    )

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        worker_send_task_events=True,
        task_send_sent_event=True,
    )

    return app


celery_app = create_celery_app() 
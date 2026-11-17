from celery import Celery
from app.config import settings

celery_app = Celery(
    "ai_interviewer",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.scoring_tasks",
        "app.tasks.pdf_tasks",
        "app.tasks.email_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.tasks.email_tasks.*": {"queue": "email"},
        "app.tasks.pdf_tasks.*": {"queue": "pdf"},
        "app.tasks.scoring_tasks.*": {"queue": "scoring"},
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

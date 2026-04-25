from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "funding_aggregator",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.collector_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        # Grants.gov — every 6 hours
        "collect-grants-gov": {
            "task": "app.tasks.collector_tasks.collect_grants_gov",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        # NIH RePORTER — daily at 3am
        "collect-nih-reporter": {
            "task": "app.tasks.collector_tasks.collect_nih_reporter",
            "schedule": crontab(minute=0, hour=3),
        },
        # USASpending.gov — daily at 4am
        "collect-usa-spending": {
            "task": "app.tasks.collector_tasks.collect_usa_spending",
            "schedule": crontab(minute=0, hour=4),
        },
    },
)

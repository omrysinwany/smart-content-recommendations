"""
Celery application configuration for background task processing.

This provides:
1. Celery app initialization
2. Task discovery and registration
3. Redis broker configuration
4. Result backend setup
5. Task routing and scheduling
"""

import os

from celery import Celery

from app.config import settings

# Create Celery instance
celery_app = Celery(
    "smart_content_recommendations",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.recommendation_tasks",
        "app.tasks.analytics_tasks",
        "app.tasks.content_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task routing
    task_routes={
        "app.tasks.recommendation_tasks.*": {"queue": "recommendations"},
        "app.tasks.analytics_tasks.*": {"queue": "analytics"},
        "app.tasks.content_tasks.*": {"queue": "content"},
    },
    # Task result settings
    result_expires=3600,  # 1 hour
    # Beat schedule for periodic tasks
    beat_schedule={
        "update-trending-content": {
            "task": "app.tasks.analytics_tasks.update_trending_content",
            "schedule": 300.0,  # Every 5 minutes
        },
        "cleanup-old-interactions": {
            "task": "app.tasks.content_tasks.cleanup_old_interactions",
            "schedule": 86400.0,  # Daily
        },
        "generate-recommendation-reports": {
            "task": "app.tasks.analytics_tasks.generate_recommendation_reports",
            "schedule": 3600.0,  # Hourly
        },
    },
    beat_schedule_filename="/tmp/celerybeat-schedule",
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Auto-discover tasks
celery_app.autodiscover_tasks()

if __name__ == "__main__":
    celery_app.start()

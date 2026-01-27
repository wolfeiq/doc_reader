import logging
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_process_shutdown
from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "doc_updater",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.query_tasks",
        "app.tasks.document_tasks",
        "app.tasks.sync_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    

    result_expires=3600,  
    result_extended=True, 

    task_acks_late=True, 
    task_reject_on_worker_lost=True,
    task_track_started=True, 
    task_time_limit=3600,  
    task_soft_time_limit=3000, 
    

    worker_prefetch_multiplier=1, 
    worker_max_tasks_per_child=100, 

    task_default_rate_limit="10/m", 
    
    task_autoretry_for=(Exception,),
    task_retry_kwargs={"max_retries": 3},
    task_retry_backoff=True,
    task_retry_backoff_max=600,  
    task_retry_jitter=True,

    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
)


celery_app.conf.task_routes = {
    "app.tasks.query_tasks.*": {"queue": "queries"},
    "app.tasks.document_tasks.*": {"queue": "documents"},
    "app.tasks.sync_tasks.*": {"queue": "maintenance"},
}

celery_app.conf.beat_schedule = {

    "health-check-every-5-minutes": {
        "task": "app.tasks.sync_tasks.health_check",
        "schedule": crontab(minute="*/5"),
    },

    "cleanup-old-queries-daily": {
        "task": "app.tasks.query_tasks.cleanup_old_queries",
        "schedule": crontab(hour=2, minute=0),
        "kwargs": {"days_old": 30},
    },

    "verify-chromadb-daily": {
        "task": "app.tasks.sync_tasks.verify_chromadb_integrity",
        "schedule": crontab(hour=3, minute=0),
    },

    "rebuild-dependencies-weekly": {
        "task": "app.tasks.sync_tasks.rebuild_all_dependencies",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
    },
}


@worker_process_init.connect
def init_worker(**kwargs):
    logger.info("Celery worker process starting...")


@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    logger.info("Celery worker process shutting down...")


if __name__ == "__main__":
    celery_app.start()
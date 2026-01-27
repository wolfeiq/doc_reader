"""
Celery Application Configuration
================================

Celery is used for background task processing, enabling:
- Async query processing (AI analysis without blocking HTTP requests)
- Document embedding generation
- Scheduled maintenance tasks (cleanup, health checks)

Architecture Decision:
----------------------
We use Celery instead of FastAPI BackgroundTasks because:
1. Tasks survive server restarts (persisted in Redis)
2. Horizontal scaling - run multiple workers
3. Task monitoring and retries built-in
4. Scheduled tasks via Celery Beat

Running Workers:
----------------
Development:
    celery -A app.celery_app worker --loglevel=info -Q queries,documents,maintenance

Production (Railway):
    Deploy as a separate service with the same codebase
    Command: celery -A app.celery_app worker --loglevel=info --concurrency=2

For scheduled tasks, also run Celery Beat:
    celery -A app.celery_app beat --loglevel=info

Production Considerations:
--------------------------
- Use separate Redis instance for Celery vs caching (isolation)
- Monitor queue depth with Flower or Prometheus
- Set up dead letter queues for failed tasks
- Consider using celery-once for distributed locks
- Implement circuit breakers for external API calls (OpenAI)
"""

import logging
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_process_shutdown
from app.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Celery Application Instance
# =============================================================================

celery_app = Celery(
    "doc_updater",
    broker=settings.redis_url,  # Redis as message broker
    backend=settings.redis_url,  # Redis for storing task results
    # Auto-discover tasks in these modules
    include=[
        "app.tasks.query_tasks",    # AI query processing
        "app.tasks.document_tasks",  # Document/embedding management
        "app.tasks.sync_tasks",      # Maintenance and sync
    ],
)

# =============================================================================
# Celery Configuration
# =============================================================================
# These settings control task behavior, reliability, and performance.
# Tuned for a balance of reliability and resource efficiency.

celery_app.conf.update(
    # --- Serialization ---
    # JSON is human-readable and secure (no pickle exploits)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # --- Result Backend ---
    result_expires=3600,  # Results expire after 1 hour (saves Redis memory)
    result_extended=True,  # Store task args/kwargs in result for debugging

    # --- Task Reliability ---
    # These settings ensure tasks aren't lost if workers crash
    task_acks_late=True,  # Ack after task completes, not when received
    task_reject_on_worker_lost=True,  # Re-queue if worker dies mid-task
    task_track_started=True,  # Track when tasks start (for monitoring)
    task_time_limit=3600,  # Hard kill after 1 hour (prevents stuck tasks)
    task_soft_time_limit=3000,  # Raise SoftTimeLimitExceeded at 50 min

    # --- Worker Settings ---
    # Conservative settings to prevent memory leaks and overload
    worker_prefetch_multiplier=1,  # Fetch 1 task at a time (fair distribution)
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (memory)

    # --- Rate Limiting ---
    # Prevents overwhelming OpenAI API and other external services
    task_default_rate_limit="10/m",  # 10 tasks per minute default

    # --- Automatic Retries ---
    # Handles transient failures (network issues, API rate limits)
    task_autoretry_for=(Exception,),  # Retry on any exception
    task_retry_kwargs={"max_retries": 3},  # Up to 3 retries
    task_retry_backoff=True,  # Exponential backoff between retries
    task_retry_backoff_max=600,  # Max 10 minutes between retries
    task_retry_jitter=True,  # Random jitter to prevent thundering herd

    # --- Broker Connection ---
    # Handles Redis connection issues gracefully
    broker_connection_retry_on_startup=True,  # Retry on startup
    broker_connection_retry=True,  # Retry on connection loss
    broker_connection_max_retries=10,  # Max reconnection attempts
)


# =============================================================================
# Task Routing
# =============================================================================
# Route tasks to specific queues for better resource management.
# This allows running separate workers for different task types.
#
# Example: Run high-priority query workers and low-priority maintenance workers:
#   celery -A app.celery_app worker -Q queries --concurrency=4
#   celery -A app.celery_app worker -Q maintenance --concurrency=1

celery_app.conf.task_routes = {
    "app.tasks.query_tasks.*": {"queue": "queries"},       # AI processing
    "app.tasks.document_tasks.*": {"queue": "documents"},  # Embeddings
    "app.tasks.sync_tasks.*": {"queue": "maintenance"},    # Background jobs
}

# =============================================================================
# Celery Beat Schedule (Periodic Tasks)
# =============================================================================
# These tasks run automatically on a schedule.
# Requires running: celery -A app.celery_app beat
#
# Production Note: For Railway, run beat in the same container as worker
# or use a separate service. Consider using django-celery-beat for
# dynamic schedules stored in database.

celery_app.conf.beat_schedule = {
    # Health check - verifies all services are operational
    # Runs every 5 minutes, useful for alerting
    "health-check-every-5-minutes": {
        "task": "app.tasks.sync_tasks.health_check",
        "schedule": crontab(minute="*/5"),
    },

    # Cleanup old queries and their suggestions
    # Runs at 2 AM UTC daily, keeps database lean
    "cleanup-old-queries-daily": {
        "task": "app.tasks.query_tasks.cleanup_old_queries",
        "schedule": crontab(hour=2, minute=0),
        "kwargs": {"days_old": 30},  # Delete queries older than 30 days
    },

    # Verify ChromaDB embeddings match database
    # Detects orphaned or missing embeddings
    "verify-chromadb-daily": {
        "task": "app.tasks.sync_tasks.verify_chromadb_integrity",
        "schedule": crontab(hour=3, minute=0),
    },

    # Rebuild document dependency graph
    # Runs weekly on Sunday at 4 AM UTC
    "rebuild-dependencies-weekly": {
        "task": "app.tasks.sync_tasks.rebuild_all_dependencies",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
    },
}


# =============================================================================
# Worker Lifecycle Hooks
# =============================================================================
# These signals fire when worker processes start/stop.
# Useful for initializing connections or cleanup.


@worker_process_init.connect
def init_worker(**kwargs):
    """
    Called when a worker process starts.

    Production Use Cases:
    - Initialize database connection pool
    - Set up monitoring/tracing
    - Load ML models into memory
    """
    logger.info("Celery worker process starting...")


@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    """
    Called when a worker process shuts down.

    Production Use Cases:
    - Close database connections
    - Flush logs/metrics
    - Cleanup temporary files
    """
    logger.info("Celery worker process shutting down...")


# Allow running celery directly: python -m app.celery_app
if __name__ == "__main__":
    celery_app.start()
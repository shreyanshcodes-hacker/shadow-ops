"""
Celery application configuration for ShadowOps background workers.

This module configures Celery for scan execution and other background tasks.
The scanner worker runs in an isolated container with strict resource limits.
"""

from celery import Celery
from celery.signals import worker_init, worker_shutdown
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "shadowops",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.scan_worker",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task tracking
    task_track_started=True,
    task_send_sent_event=True,
    
    # Worker configuration
    worker_prefetch_multiplier=1,  # One task per worker at a time
    worker_max_tasks_per_child=10,  # Recycle worker after 10 tasks
    worker_disable_rate_limits=True,
    
    # Task time limits (seconds)
    task_soft_time_limit=1800,  # 30 minutes soft limit
    task_time_limit=1860,  # 31 minutes hard limit (allows cleanup)
    
    # Result backend
    result_expires=86400,  # 24 hours
    result_compression="gzip",
    
    # Task routing
    task_routes={
        "app.workers.scan_worker.execute_scan_job": {"queue": "scans"},
        "app.workers.scan_worker.cancel_scan_job": {"queue": "scans"},
    },
    
    # Task acknowledgment
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Monitoring
    worker_send_task_events=True,
    
    # Security: Don't store sensitive data in results
    result_extended=True,
)


@worker_init.connect
def init_worker(**kwargs):
    """Initialize worker process."""
    logger.info("Scanner worker initializing")
    # Set up any worker-specific initialization here
    # e.g., verify semgrep binary exists, check resource limits


@worker_shutdown.connect
def shutdown_worker(**kwargs):
    """Clean up worker process."""
    logger.info("Scanner worker shutting down")


# Health check task
@celery_app.task(bind=True, name="app.workers.health_check")
def health_check(self):
    """Worker health check endpoint."""
    return {"status": "healthy", "worker": self.request.hostname}
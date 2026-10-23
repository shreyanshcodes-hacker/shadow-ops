"""
ShadowOps Workers Package

This package contains Celery worker tasks for background job processing.
The scan worker runs in an isolated container with strict security constraints.
"""

from app.workers.celery_app import celery_app
from app.workers.scan_worker import execute_scan_job, cancel_scan_job

__all__ = [
    "celery_app",
    "execute_scan_job",
    "cancel_scan_job",
]
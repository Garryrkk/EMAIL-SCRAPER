import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

from app.workers.tasks import (
    cleanup_old_data_task,
    update_bounce_stats_task,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def start_scheduler():
    """Start background task scheduler."""
    if scheduler.running:
        return

    # Schedule tasks
    scheduler.add_job(
        cleanup_old_data_task,
        trigger="cron",
        hour=2,  # 2 AM UTC daily
        id="cleanup_old_data",
        name="Cleanup old data",
    )

    scheduler.add_job(
        update_bounce_stats_task,
        trigger="cron",
        hour="*/6",  # Every 6 hours
        id="update_bounce_stats",
        name="Update bounce statistics",
    )

    scheduler.start()
    logger.info("Task scheduler started")


async def stop_scheduler():
    """Stop background task scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Task scheduler stopped")
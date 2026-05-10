"""APScheduler configuration for the brain reasoning cycle."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from src.config import get_settings

settings = get_settings()

JOB_ID = "brain_cycle"


class BotScheduler:
    """Manages the APScheduler for the brain cycle."""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._is_paused = False
        self._last_run: Optional[datetime] = None

    def start(self, interval_seconds: Optional[int] = None) -> None:
        interval = interval_seconds or settings.brain_cycle_interval_seconds

        async def _run_cycle_job() -> None:
            from src.brain import get_brain
            brain = get_brain()
            if self._is_paused:
                logger.debug("Scheduler paused, skipping cycle")
                return
            self._last_run = datetime.utcnow()
            try:
                result = await brain.run_cycle()
                logger.info(
                    f"Scheduled cycle #{result.get('cycle_number')} done: "
                    f"action={result.get('action')}, "
                    f"confidence={result.get('confidence', 0):.2f}, "
                    f"duration={result.get('duration_ms')}ms"
                )
            except Exception as exc:
                logger.error(f"Scheduled brain cycle error: {exc}")

        self._scheduler.add_job(
            _run_cycle_job,
            trigger=IntervalTrigger(seconds=interval),
            id=JOB_ID,
            name="Brain Reasoning Cycle",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )

        self._scheduler.start()
        logger.info(f"Scheduler started — brain cycle every {interval}s")

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def pause(self) -> None:
        self._is_paused = True
        logger.info("Brain cycle paused")

    def resume(self) -> None:
        self._is_paused = False
        logger.info("Brain cycle resumed")

    def trigger_now(self) -> None:
        self._scheduler.modify_job(JOB_ID, next_run_time=datetime.utcnow())

    def update_interval(self, seconds: int) -> None:
        self._scheduler.reschedule_job(
            JOB_ID,
            trigger=IntervalTrigger(seconds=seconds),
        )
        logger.info(f"Scheduler interval updated to {seconds}s")

    def get_status(self) -> dict[str, Any]:
        job = self._scheduler.get_job(JOB_ID)
        next_run = None
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
        return {
            "running": self._scheduler.running,
            "paused": self._is_paused,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "next_run": next_run,
            "interval_seconds": settings.brain_cycle_interval_seconds,
        }


_scheduler: Optional[BotScheduler] = None


def get_scheduler() -> BotScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BotScheduler()
    return _scheduler

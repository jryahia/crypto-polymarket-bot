"""Aether Trading Bot — Entry point.

Starts FastAPI + uvicorn in a background thread, launches APScheduler for
the brain cycle, then opens the Flet desktop UI.

Usage:
    python main.py              # Full mode: API + Scheduler + UI
    python main.py --api-only   # API + Scheduler only (no desktop window; for Docker)
    python main.py --no-ui      # Same as --api-only
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import threading

import uvicorn
from loguru import logger


def _configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> — {message}",
        level=log_level,
        colorize=True,
    )
    os.makedirs("logs", exist_ok=True)
    logger.add(
        "logs/aether.log",
        rotation="50 MB",
        retention="14 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} — {message}",
    )


def _create_directories() -> None:
    for path in ["data/db", "data/chroma", "logs", "soul", "skills"]:
        os.makedirs(path, exist_ok=True)


def _start_api_server_thread(host: str, port: int) -> threading.Thread:
    """Run uvicorn in a daemon thread."""
    from src.api_server import app

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        loop="asyncio",
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    def _run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    thread = threading.Thread(target=_run, daemon=True, name="uvicorn")
    thread.start()
    logger.info(f"API server started on http://{host}:{port}")
    return thread


def _start_scheduler(loop: asyncio.AbstractEventLoop) -> None:
    """Start APScheduler on the given event loop."""
    from src.scheduler import get_scheduler
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Scheduler started")


async def _async_startup() -> None:
    """Perform async startup tasks: DB init, soul seed."""
    from src.database import init_db
    from src.soul_manager import get_soul_manager

    await init_db()
    soul_manager = get_soul_manager()
    await soul_manager.ensure_soul_exists()
    logger.info("Startup complete — DB initialized, soul loaded")


def _run_api_and_scheduler() -> None:
    """Run the API server and scheduler in API-only mode (blocking)."""
    from src.config import get_settings
    settings = get_settings()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_async_startup())

    from src.api_server import app
    from src.scheduler import get_scheduler

    scheduler = get_scheduler()
    scheduler.start()

    config = uvicorn.Config(
        app=app,
        host=settings.app_host,
        port=settings.app_port,
        loop="asyncio",
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


def _run_full() -> None:
    """Run API server + scheduler in background, then launch Flet UI."""
    from src.config import get_settings
    settings = get_settings()

    asyncio.run(_async_startup())

    api_thread = _start_api_server_thread(settings.app_host, settings.app_port)

    import time
    time.sleep(1.5)

    from src.scheduler import get_scheduler
    scheduler = get_scheduler()
    scheduler.start()

    logger.info("Launching Flet UI...")
    from src.ui.app import run_ui
    run_ui()

    scheduler.stop()
    logger.info("Aether shutdown complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aether Trading Bot")
    parser.add_argument(
        "--api-only", "--no-ui",
        action="store_true",
        help="Run API + Scheduler only, no desktop UI (for server/Docker deployment)",
    )
    args = parser.parse_args()

    _configure_logging()
    _create_directories()

    logger.info("=" * 60)
    logger.info("  Aether Autonomous Trading Bot — Starting")
    logger.info("=" * 60)

    if args.api_only:
        logger.info("Mode: API-only (no UI)")
        _run_api_and_scheduler()
    else:
        logger.info("Mode: Full (API + Scheduler + UI)")
        _run_full()


if __name__ == "__main__":
    main()

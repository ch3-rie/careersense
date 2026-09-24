"""Background email worker: outbox retries and due profile reminders."""

from __future__ import annotations

import asyncio
import logging

from app.config import get_settings
from app.db import SessionLocal
from app.services.email.outbox import process_outbox
from app.services.email.service import scheduler_is_enabled, sending_enabled
from app.services.profile_reminders import maybe_run_due_reminders

logger = logging.getLogger("careersense")


def tick() -> None:
    db = SessionLocal()
    try:
        if sending_enabled():
            processed = process_outbox(db)
            if processed:
                db.commit()
            else:
                db.rollback()
        else:
            db.rollback()
        maybe_run_due_reminders(db)
    except Exception:
        db.rollback()
        logger.exception("Email scheduler tick failed")
    finally:
        db.close()


async def run_email_scheduler(stop: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(15, int(getattr(settings, "email_scheduler_interval_seconds", 60) or 60))
    logger.info("Email scheduler started interval=%ss", interval)
    try:
        while not stop.is_set():
            try:
                await asyncio.to_thread(tick)
            except Exception:
                logger.exception("Email scheduler worker failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        raise
    finally:
        logger.info("Email scheduler stopped")

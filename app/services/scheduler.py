import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.services.email import run_inactive_scan, process_scheduled_sends

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="Asia/Hong_Kong")


def _scan_job():
    db = SessionLocal()
    try:
        count = run_inactive_scan(db)
        logger.info(f"[Scheduler] Weekly scan complete – {count} drafts created")
    except Exception as e:
        logger.error(f"[Scheduler] Weekly scan error: {e}")
    finally:
        db.close()


def _send_job():
    db = SessionLocal()
    try:
        count = process_scheduled_sends(db)
        if count:
            logger.info(f"[Scheduler] Sent {count} emails")
    except Exception as e:
        logger.error(f"[Scheduler] Send job error: {e}")
    finally:
        db.close()


def start_scheduler():
    # Weekly scan: every Monday at 09:00 HKT
    _scheduler.add_job(
        _scan_job,
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="weekly_scan",
        replace_existing=True,
    )
    # Process pending sends: every minute
    _scheduler.add_job(
        _send_job,
        IntervalTrigger(minutes=1),
        id="send_emails",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("[Scheduler] Started – weekly scan (Mon 09:00) + per-minute sender")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped")

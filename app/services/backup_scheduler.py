"""Ежедневный планировщик бэкапов БД в Telegram."""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_backup_scheduler() -> AsyncIOScheduler:
    """Запускает планировщик ежедневных бэкапов в 22:00."""
    from ..database import get_app_settings, get_db_path
    from .telegram_bot import send_backup

    scheduler = AsyncIOScheduler()

    def job():
        settings = get_app_settings([
            "telegram_bot_token",
            "telegram_chat_id",
            "telegram_backup_enabled",
        ])
        if settings.get("telegram_backup_enabled", "false") != "true":
            logger.info("Telegram backup disabled — skipping")
            return

        bot_token = settings.get("telegram_bot_token", "").strip()
        chat_id = settings.get("telegram_chat_id", "").strip()

        if not bot_token or not chat_id:
            logger.warning("Telegram backup: missing bot_token or chat_id — skipping")
            return

        db_path = get_db_path()
        success = send_backup(bot_token, chat_id, db_path)

        if success:
            logger.info("Daily Telegram backup: SUCCESS")
        else:
            logger.error("Daily Telegram backup: FAILED")

    scheduler.add_job(
        job,
        CronTrigger(hour=22, minute=0, timezone='Asia/Vladivostok'),
        id="daily_db_backup",
        name="Daily database backup to Telegram",
        replace_existing=True,
        max_instances=1,
    )

    global _scheduler
    _scheduler = scheduler
    scheduler.start()
    logger.info("Backup scheduler started — daily at 22:00 Asia/Vladivostok (UTC+10)")

    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Backup scheduler stopped")

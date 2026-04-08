"""Telegram Bot API helper — raw httpx calls, no aiogram needed."""
import httpx
import io
import zipfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _make_url(token: str, method: str) -> str:
    return TELEGRAM_API.format(token=token, method=method)


def send_text_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Отправляет текстовое сообщение в Telegram."""
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                _make_url(bot_token, "sendMessage"),
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            resp.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Telegram send_text_message error: {e}")
        return False


def send_backup(bot_token: str, chat_id: str, db_path: Path) -> bool:
    """Создаёт ZIP-архив БД и отправляет в Telegram как документ."""
    try:
        data_dir = db_path.parent

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            if db_path.exists():
                zf.write(db_path, db_path.name)
            for ext in ("-shm", "-wal"):
                sibling = db_path.with_name(db_path.stem + ".db" + ext)
                if sibling.exists():
                    zf.write(sibling, sibling.name)
            for f in data_dir.iterdir():
                if f.name not in (db_path.name, db_path.stem + ".db-shm", db_path.stem + ".db-wal"):
                    zf.write(f, f.name)

        zip_buffer.seek(0)

        timestamp = __import__("time").strftime("%Y-%m-%d %H:%M")
        caption = f"Автоматический бэкап БД — {timestamp}"

        with httpx.Client(timeout=120) as client:
            resp = client.post(
                _make_url(bot_token, "sendDocument"),
                data={"chat_id": chat_id, "caption": caption},
                files={
                    "document": (f"ekc_backup_{__import__('time').strftime('%Y%m%d')}.zip", zip_buffer, "application/zip"),
                },
            )
            resp.raise_for_status()
            logger.info("Telegram backup sent successfully")
            return True

    except Exception as e:
        logger.error(f"Telegram send_backup error: {e}")
        return False

import os
import shutil
import time
from pathlib import Path
from typing import Optional
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from bot.config import DOWNLOAD_DIR
from bot.database.models import get_expired_messages, delete_tracked_records
from bot.utils.logger import logger

async def auto_delete_expired_messages_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Scheduled JobQueue worker that deletes messages older than 24 hours
    from both Telegram chat and the SQLite tracker table.
    """
    try:
        now = int(time.time())
        expired_records = await get_expired_messages(now)
        if not expired_records:
            return

        logger.info("Auto-cleaner found %d expired messages to delete.", len(expired_records))
        record_ids_to_remove = []

        for record in expired_records:
            chat_id = record["chat_id"]
            message_id = record["message_id"]
            record_id = record["id"]

            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.debug("Successfully auto-deleted message %s in chat %s", message_id, chat_id)
            except TelegramError as e:
                # If message was already deleted by user or permissions issue, log and continue
                logger.debug("Could not delete message %s in chat %s: %s", message_id, chat_id, e)
            
            record_ids_to_remove.append(record_id)

        if record_ids_to_remove:
            await delete_tracked_records(record_ids_to_remove)
            logger.info("Purged %d expired records from message tracker.", len(record_ids_to_remove))

    except Exception as e:
        logger.error("Error in auto_delete_expired_messages_job: %s", e)

def cleanup_orphaned_temp_files(max_age_seconds: int = 3600 * 2) -> int:
    """
    Garbage collector to remove dangling directories in downloads/
    older than max_age_seconds (default: 2 hours).
    """
    if not DOWNLOAD_DIR.exists():
        return 0

    now = time.time()
    deleted_count = 0

    for item in DOWNLOAD_DIR.iterdir():
        if item.is_dir():
            try:
                mtime = item.stat().st_mtime
                if now - mtime > max_age_seconds:
                    shutil.rmtree(item, ignore_errors=True)
                    deleted_count += 1
            except Exception as e:
                logger.warning("Failed to remove orphaned temp dir %s: %s", item, e)

    if deleted_count > 0:
        logger.info("Cleaned up %d orphaned temporary download directories.", deleted_count)
    return deleted_count

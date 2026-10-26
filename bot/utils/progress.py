import time
from typing import Optional, Callable
from telegram import Message
from telegram.error import TelegramError
from bot.utils.helpers import format_size, format_duration
from bot.utils.logger import logger

class ProgressTracker:
    """
    Manages live status updates for a Telegram status message.
    Throttles updates to respect Telegram rate limits.
    """

    def __init__(self, message: Message, update_interval: float = 2.5):
        self.message = message
        self.update_interval = update_interval
        self.last_update_time = 0.0
        self.last_text = ""
        self.current_phase = "Initializing..."

    def create_progress_bar(self, percentage: float, length: int = 10) -> str:
        """Generates a visual progress bar e.g. [▰▰▰▰▱▱▱▱▱▱] 40%"""
        percentage = max(0.0, min(100.0, percentage))
        filled = int((percentage / 100.0) * length)
        empty = length - filled
        bar = "▰" * filled + "▱" * empty
        return f"[{bar}] {percentage:.1f}%"

    async def update_status(self, text: str, force: bool = False) -> None:
        """Edits the Telegram message with updated status text."""
        now = time.time()
        if not force and (now - self.last_update_time < self.update_interval):
            return

        if text == self.last_text:
            return

        try:
            self.last_text = text
            self.last_update_time = now
            await self.message.edit_text(text, parse_mode="HTML")
        except TelegramError as e:
            # Ignore "Message is not modified" or transient network errors
            if "Message is not modified" not in str(e):
                logger.debug("Failed to update progress message: %s", e)

    def ytdl_hook(self, d: dict) -> None:
        """yt-dlp download progress hook (runs in downloader thread)."""
        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            speed = d.get("speed", 0)
            eta = d.get("eta", 0)

            pct = (downloaded / total * 100) if total > 0 else 0
            bar = self.create_progress_bar(pct)

            speed_str = f"{format_size(speed)}/s" if speed else "N/A"
            eta_str = format_duration(eta) if eta else "calculating..."
            size_str = f"{format_size(downloaded)} / {format_size(total)}" if total else format_size(downloaded)

            text = (
                f"<b>⬇️ Downloading Media...</b>\n\n"
                f"<code>{bar}</code>\n"
                f"<b>📊 Progress:</b> {size_str}\n"
                f"<b>⚡ Speed:</b> {speed_str}\n"
                f"<b>⏱️ ETA:</b> {eta_str}"
            )
            self.current_phase = text
        elif status == "finished":
            self.current_phase = "<b>⚙️ Download complete. Processing media with FFmpeg...</b>"

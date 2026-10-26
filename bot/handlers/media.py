import uuid
from typing import Dict, Any
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from bot.config import PLATFORM_EMOJIS
from bot.database.models import upsert_user, is_user_banned, track_message
from bot.services.url_detector import extract_urls, detect_platform
from bot.services.downloader import MediaDownloader
from bot.services.rate_limiter import rate_limiter
from bot.utils.helpers import format_duration, safe_html, truncate_text
from bot.utils.logger import logger

# In-memory store for pending download requests keyed by a short token
PENDING_REQUESTS: Dict[str, Dict[str, Any]] = {}

def get_format_selection_keyboard(token: str) -> InlineKeyboardMarkup:
    """Returns format selection buttons (Video, Audio, Cancel)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Video (MP4)", callback_data=f"dl:video:{token}"),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"dl:audio:{token}")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"dl:cancel:{token}")
        ]
    ])

async def handle_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles messages containing URLs or /send command."""
    if not update.effective_user or not update.effective_message:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    message_text = update.effective_message.text or update.effective_message.caption or ""

    # Ensure user is registered
    await upsert_user(user.id, user.username, user.first_name)

    # Check ban status
    if await is_user_banned(user.id):
        sent = await update.effective_message.reply_text(
            "⛔ <b>Access Denied:</b> Your account has been suspended from using this bot.",
            parse_mode="HTML"
        )
        await track_message(chat_id, sent.message_id, user.id)
        return

    # Check rate limit
    is_limited, wait_seconds = rate_limiter.is_rate_limited(user.id)
    if is_limited:
        sent = await update.effective_message.reply_text(
            f"⏳ <b>Rate Limit Reached:</b> Please wait <b>{wait_seconds}s</b> before requesting another download.",
            parse_mode="HTML"
        )
        await track_message(chat_id, sent.message_id, user.id)
        return

    # Extract URLs from message
    urls = extract_urls(message_text)
    if not urls:
        # If user explicitly used /send without URL
        if message_text.startswith("/send"):
            sent = await update.effective_message.reply_text(
                "ℹ️ <b>Usage:</b> <code>/send &lt;media_url&gt;</code>\n"
                "Example: <code>/send https://www.youtube.com/watch?v=...</code>",
                parse_mode="HTML"
            )
            await track_message(chat_id, sent.message_id, user.id)
        return

    target_url = urls[0]
    platform_key, platform_name = detect_platform(target_url)
    emoji_platform = PLATFORM_EMOJIS.get(platform_key, "🌐 Web Media")

    # Track user's URL message for 24h auto-deletion
    await track_message(chat_id, update.effective_message.message_id, user.id)

    # Send analyzing status message
    status_msg = await update.effective_message.reply_text(
        f"🔍 <b>Analyzing URL...</b>\n\n"
        f"<b>Platform:</b> {emoji_platform}\n"
        f"<i>Fetching media details, please wait...</i>",
        parse_mode="HTML"
    )
    await track_message(chat_id, status_msg.message_id, user.id)

    # Extract metadata using yt-dlp
    info = await MediaDownloader.extract_media_info(target_url)
    if not info:
        # Fallback metadata if pre-fetching is restricted by platform
        from bot.services.downloader import MediaInfo
        info = MediaInfo(
            title=f"{platform_name} Media",
            duration=0,
            uploader="Web Post",
            thumbnail_url=None,
            platform=platform_key,
            views=None,
            is_playlist=False,
            entries_count=1
        )

    # Store request metadata with a short unique token
    token = str(uuid.uuid4())[:8]
    PENDING_REQUESTS[token] = {
        "url": target_url,
        "platform": platform_key,
        "title": info.title,
        "duration": info.duration,
        "user_id": user.id,
        "chat_id": chat_id,
        "status_message_id": status_msg.message_id
    }

    duration_str = format_duration(info.duration) if info.duration > 0 else "Live/Dynamic"
    title_escaped = safe_html(truncate_text(info.title, 80))
    uploader_escaped = safe_html(truncate_text(info.uploader, 40))

    preview_text = (
        f"<b>🎬 Media Found!</b>\n\n"
        f"📌 <b>Title:</b> {title_escaped}\n"
        f"👤 <b>Author:</b> {uploader_escaped}\n"
        f"⏱️ <b>Duration:</b> {duration_str}\n"
        f"🌐 <b>Platform:</b> {emoji_platform}\n\n"
        f"<i>Select your desired format below:</i>"
    )

    await status_msg.edit_text(
        preview_text,
        parse_mode="HTML",
        reply_markup=get_format_selection_keyboard(token)
    )

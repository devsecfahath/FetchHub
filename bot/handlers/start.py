from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from bot.database.models import upsert_user, get_user_stats, track_message
from bot.utils.helpers import safe_html
from bot.utils.logger import logger

START_BANNER = """
<b>🚀 Welcome to Media Downloader Bot!</b>

Send me any media link from your favorite platforms, and I'll fetch it for you in high quality!

<b>✨ Supported Platforms:</b>
• 🔴 <b>YouTube:</b> Videos, Shorts, MP3 Audio
• 📸 <b>Instagram:</b> Reels, Posts, Stories
• 🎵 <b>TikTok:</b> Videos (No Watermark)
• 🔵 <b>Facebook:</b> Reels & Public Videos
• 🐦 <b>X (Twitter):</b> Videos & GIFs
• 🌐 <b>Web:</b> Reddit, Pinterest, & more

<b>⚡ Features:</b>
• 🎬 High Quality MP4 Video
• 🎵 320kbps / 192kbps MP3 Audio
• ✂️ Smart Compression (under 50MB)
• 🧹 <b>24-Hour Auto-Delete</b> chat history cleanup

<i>Just paste a link below to get started!</i>
"""

HELP_TEXT = """
<b>📖 How to Use the Bot:</b>

1️⃣ <b>Direct Link:</b> Simply copy and paste any video or post link directly into this chat.
2️⃣ <b>Format Selection:</b> Choose between <b>🎬 Video</b> or <b>🎵 Audio (MP3)</b>.
3️⃣ <b>Automatic Processing:</b> The bot will download, process thumbnail, compress (if needed), and send the media right back to you!

<b>🛠 Commands:</b>
• /start - Start or restart the bot
• /send <code>&lt;URL&gt;</code> - Download media via command
• /mystats - View your personal download history
• /help - Display this help guide
• /about - Learn more about the bot
"""

ABOUT_TEXT = """
<b>ℹ️ About Media Downloader Bot</b>

• <b>Version:</b> 1.0.0
• <b>Engine:</b> Python 3.12 + python-telegram-bot + yt-dlp + FFmpeg
• <b>Privacy:</b> All chat messages and temporary media are automatically purged after <b>24 hours</b>.
• <b>Speed:</b> Ultra-fast downloads with dynamic video compression.
"""

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Returns main inline navigation buttons."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Help Guide", callback_data="nav:help"),
            InlineKeyboardButton("📊 My Stats", callback_data="nav:stats")
        ],
        [
            InlineKeyboardButton("ℹ️ About", callback_data="nav:about")
        ]
    ])

def get_back_keyboard() -> InlineKeyboardMarkup:
    """Returns a Back to Home button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Home", callback_data="nav:start")]
    ])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start command."""
    if not update.effective_user or not update.effective_message:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id

    # Register user in database
    await upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )

    # Track user's /start message for auto-deletion
    await track_message(chat_id=chat_id, message_id=update.effective_message.message_id, user_id=user.id)

    sent = await update.effective_message.reply_text(
        START_BANNER,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

    # Track bot's reply message for 24h auto-deletion
    await track_message(chat_id=chat_id, message_id=sent.message_id, user_id=user.id)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /help command."""
    if not update.effective_message or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    await track_message(chat_id=chat_id, message_id=update.effective_message.message_id, user_id=update.effective_user.id)

    sent = await update.effective_message.reply_text(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await track_message(chat_id=chat_id, message_id=sent.message_id, user_id=update.effective_user.id)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /about command."""
    if not update.effective_message or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    await track_message(chat_id=chat_id, message_id=update.effective_message.message_id, user_id=update.effective_user.id)

    sent = await update.effective_message.reply_text(
        ABOUT_TEXT,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await track_message(chat_id=chat_id, message_id=sent.message_id, user_id=update.effective_user.id)

async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /mystats command."""
    if not update.effective_user or not update.effective_message:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    stats = await get_user_stats(user_id)

    platforms_str = ""
    if stats["platform_breakdown"]:
        for plat, count in stats["platform_breakdown"].items():
            platforms_str += f"  • <b>{plat.capitalize()}:</b> {count}\n"
    else:
        platforms_str = "  <i>No downloads yet.</i>\n"

    text = (
        f"<b>📊 Your Download Statistics:</b>\n\n"
        f"👤 <b>User:</b> {safe_html(update.effective_user.first_name)}\n"
        f"📥 <b>Total Downloads:</b> {stats['total_downloads']}\n"
        f"📅 <b>Member Since:</b> {stats['created_at']}\n\n"
        f"<b>🌐 Breakdown by Platform:</b>\n{platforms_str}"
    )

    await track_message(chat_id=chat_id, message_id=update.effective_message.message_id, user_id=user_id)
    sent = await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await track_message(chat_id=chat_id, message_id=sent.message_id, user_id=user_id)

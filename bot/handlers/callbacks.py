import os
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.media import PENDING_REQUESTS
from bot.handlers.start import START_BANNER, HELP_TEXT, ABOUT_TEXT, get_main_keyboard, get_back_keyboard
from bot.services.downloader import MediaDownloader, DownloadResult
from bot.database.models import log_download, get_user_stats, track_message
from bot.utils.progress import ProgressTracker
from bot.utils.helpers import format_size, format_duration, safe_html, truncate_text
from bot.utils.logger import logger

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatches inline button callbacks."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id if user else 0

    # Navigation callbacks
    if data == "nav:start":
        await query.edit_message_text(START_BANNER, parse_mode="HTML", reply_markup=get_main_keyboard())
        return
    elif data == "nav:help":
        await query.edit_message_text(HELP_TEXT, parse_mode="HTML", reply_markup=get_back_keyboard())
        return
    elif data == "nav:about":
        await query.edit_message_text(ABOUT_TEXT, parse_mode="HTML", reply_markup=get_back_keyboard())
        return
    elif data == "nav:stats":
        stats = await get_user_stats(user_id)
        platforms_str = ""
        if stats["platform_breakdown"]:
            for plat, count in stats["platform_breakdown"].items():
                platforms_str += f"  • <b>{plat.capitalize()}:</b> {count}\n"
        else:
            platforms_str = "  <i>No downloads yet.</i>\n"

        text = (
            f"<b>📊 Your Download Statistics:</b>\n\n"
            f"👤 <b>User:</b> {safe_html(user.first_name if user else 'User')}\n"
            f"📥 <b>Total Downloads:</b> {stats['total_downloads']}\n"
            f"📅 <b>Member Since:</b> {stats['created_at']}\n\n"
            f"<b>🌐 Breakdown by Platform:</b>\n{platforms_str}"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_back_keyboard())
        return

    # Download callbacks (format: dl:<action>:<token>)
    if data.startswith("dl:"):
        parts = data.split(":")
        if len(parts) != 3:
            return

        action, token = parts[1], parts[2]
        request_data = PENDING_REQUESTS.get(token)

        if not request_data:
            await query.edit_message_text(
                "⚠️ <b>Session Expired:</b> This download request is no longer valid. Please send the link again.",
                parse_mode="HTML"
            )
            return

        if action == "cancel":
            PENDING_REQUESTS.pop(token, None)
            await query.edit_message_text("❌ <b>Download Cancelled.</b>", parse_mode="HTML")
            return

        # Start downloading
        url = request_data["url"]
        platform = request_data["platform"]
        format_type = "audio" if action == "audio" else "video"

        # Remove from pending requests
        PENDING_REQUESTS.pop(token, None)

        progress = ProgressTracker(query.message)
        await progress.update_status(
            f"⏳ <b>Initializing Download...</b>\n\n"
            f"<b>Format:</b> {'🎵 Audio (MP3)' if format_type == 'audio' else '🎬 Video (MP4)'}\n"
            f"<i>Connecting to media stream...</i>",
            force=True
        )

        result: Optional[DownloadResult] = None
        try:
            # Download and process media
            result = await MediaDownloader.download(
                url=url,
                format_type=format_type,
                progress_hook=progress.ytdl_hook
            )

            await progress.update_status(
                "<b>⬆️ Uploading to Telegram...</b>\n\n"
                f"<b>File:</b> {safe_html(truncate_text(result.title, 50))}\n"
                f"<b>Size:</b> {format_size(result.file_size)}\n"
                f"<i>Please hold on...</i>",
                force=True
            )

            caption = (
                f"<b>{safe_html(truncate_text(result.title, 80))}</b>\n\n"
                f"⏱️ <b>Duration:</b> {format_duration(result.duration)}\n"
                f"📦 <b>Size:</b> {format_size(result.file_size)}\n"
                f"🤖 <i>Downloaded via @{context.bot.username or 'MediaDownloaderBot'}</i>"
            )

            sent_media_msg = None
            if result.file_type == "video":
                thumb_file = open(result.thumbnail_path, "rb") if result.thumbnail_path and result.thumbnail_path.exists() else None
                try:
                    with open(result.file_path, "rb") as video_file:
                        sent_media_msg = await context.bot.send_video(
                            chat_id=chat_id,
                            video=video_file,
                            duration=result.duration,
                            width=result.width,
                            height=result.height,
                            thumbnail=thumb_file,
                            caption=caption,
                            parse_mode="HTML",
                            supports_streaming=True,
                            read_timeout=300.0,
                            write_timeout=300.0,
                            connect_timeout=60.0
                        )
                finally:
                    if thumb_file:
                        thumb_file.close()

            elif result.file_type == "audio":
                with open(result.file_path, "rb") as audio_file:
                    sent_media_msg = await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=audio_file,
                        title=result.title,
                        duration=result.duration,
                        caption=caption,
                        parse_mode="HTML",
                        read_timeout=300.0,
                        write_timeout=300.0,
                        connect_timeout=60.0
                    )

            # Record in SQLite database
            await log_download(
                user_id=user_id,
                url=url,
                platform=platform,
                file_type=format_type,
                file_size=result.file_size,
                status="success"
            )

            # Track sent media message for 24-hour auto-deletion
            if sent_media_msg:
                await track_message(chat_id, sent_media_msg.message_id, user_id)

            # Clean up the status message
            try:
                await query.message.delete()
            except Exception:
                pass

        except Exception as e:
            logger.error("Error during download callback: %s", e)
            await log_download(
                user_id=user_id,
                url=url,
                platform=platform,
                file_type=format_type,
                file_size=0,
                status="failed",
                error_message=str(e)
            )
            err_text = str(e)
            if "429" in err_text or "Too Many Requests" in err_text or "COOKIES_TEXT" in err_text:
                error_msg = (
                    "❌ <b>Instagram Blocked the Download</b>\n\n"
                    "Instagram is blocking requests from cloud servers.\n\n"
                    "🔧 <b>How to fix it (2 minutes):</b>\n"
                    "1. Install <b>Get cookies.txt LOCALLY</b> browser extension\n"
                    "2. Open Instagram.com while logged in\n"
                    "3. Click the extension → Export cookies\n"
                    "4. Paste it in Render → Environment → <code>COOKIES_TEXT</code>"
                )
            else:
                error_msg = (
                    f"❌ <b>Download Failed</b>\n\n"
                    f"<b>Reason:</b> {safe_html(err_text)}\n\n"
                    f"<i>Please verify the link is accessible and try again.</i>"
                )
            await progress.update_status(error_msg, force=True)


        finally:
            if result:
                result.cleanup()

import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from bot.config import ADMIN_IDS
from bot.database.models import (
    get_admin_stats,
    set_user_ban_status,
    get_all_user_ids,
    track_message
)
from bot.services.cleaner import auto_delete_expired_messages_job, cleanup_orphaned_temp_files
from bot.utils.helpers import format_size, safe_html
from bot.utils.logger import logger

def is_admin(user_id: int) -> bool:
    """Checks if the user is in the authorized admin list."""
    return user_id in ADMIN_IDS

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /admin command."""
    if not update.effective_user or not update.effective_message:
        return

    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.effective_message.reply_text("⛔ You are not authorized to use admin commands.")
        return

    text = (
        "<b>👑 Admin Control Panel</b>\n\n"
        "<b>Available Admin Commands:</b>\n"
        "• <code>/stats</code> - View bot metrics & platform breakdown\n"
        "• <code>/users</code> - List recent users with their Telegram IDs\n"
        "• <code>/find &lt;username/id&gt;</code> - Search for a user's ID\n"
        "• <code>/broadcast &lt;msg&gt;</code> - Broadcast announcement to all users\n"
        "• <code>/ban &lt;user_id&gt;</code> - Ban user (or reply /ban to a user's forwarded msg)\n"
        "• <code>/unban &lt;user_id&gt;</code> - Unban user\n"
        "• <code>/cleanup</code> - Force run 24h chat cleanup & temp file purge"
    )
    await update.effective_message.reply_text(text, parse_mode="HTML")

async def users_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /users command to view recent users and their IDs."""
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        return

    from bot.database.models import get_recent_users
    users = await get_recent_users(limit=20)
    if not users:
        await update.effective_message.reply_text("No users found in database.")
        return

    lines = ["<b>👥 Recent Bot Users:</b>\n"]
    for u in users:
        status_emoji = "🚫 [BANNED]" if u.get("is_banned") else "🟢"
        uname = f"@{u['username']}" if u.get("username") else "No username"
        name = safe_html(u.get("first_name") or "User")
        uid = u["user_id"]
        dl = u.get("total_downloads", 0)
        lines.append(f"{status_emoji} <b>{name}</b> ({uname})\n   └ 🆔 <code>{uid}</code> | 📥 {dl} downloads\n")

    lines.append("<i>💡 Tap on any User ID to copy it.</i>")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")

async def find_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /find <username or id> to lookup user ID and status."""
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.effective_message.reply_text("ℹ️ <b>Usage:</b> <code>/find &lt;username or user_id&gt;</code>", parse_mode="HTML")
        return

    from bot.database.models import search_users
    query = " ".join(context.args)
    results = await search_users(query)

    if not results:
        await update.effective_message.reply_text(f"⚠️ No user matching '<code>{safe_html(query)}</code>' found in database.", parse_mode="HTML")
        return

    lines = [f"<b>🔍 Search Results for '{safe_html(query)}':</b>\n"]
    for u in results:
        status = "🚫 BANNED" if u.get("is_banned") else "🟢 Active"
        uname = f"@{u['username']}" if u.get("username") else "None"
        name = safe_html(u.get("first_name") or "User")
        uid = u["user_id"]
        dl = u.get("total_downloads", 0)
        lines.append(
            f"• <b>{name}</b> ({uname})\n"
            f"  └ 🆔 <code>{uid}</code>\n"
            f"  └ 📊 Status: {status} | Downloads: {dl}\n"
            f"  └ Ban command: <code>/ban {uid}</code>\n"
        )

    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /ban <user_id> or replying /ban to a forwarded message."""
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        return

    target_id = None

    # Check if replying to a forwarded message
    if update.effective_message.reply_to_message:
        replied = update.effective_message.reply_to_message
        if replied.forward_from:
            target_id = replied.forward_from.id
        elif replied.from_user:
            target_id = replied.from_user.id

    # If argument provided, override
    if context.args and context.args[0].isdigit():
        target_id = int(context.args[0])

    if not target_id:
        await update.effective_message.reply_text(
            "ℹ️ <b>Usage:</b>\n"
            "• <code>/ban &lt;user_id&gt;</code>\n"
            "• Or reply <code>/ban</code> directly to a user's forwarded message.\n"
            "• Use <code>/users</code> to find all User IDs.",
            parse_mode="HTML"
        )
        return

    success = await set_user_ban_status(target_id, is_banned=True)
    if success:
        await update.effective_message.reply_text(f"🚫 User <code>{target_id}</code> has been banned from using the bot.", parse_mode="HTML")
    else:
        await update.effective_message.reply_text(f"⚠️ User <code>{target_id}</code> not found in database.", parse_mode="HTML")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /unban <user_id>."""
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        return

    target_id = None
    if update.effective_message.reply_to_message:
        replied = update.effective_message.reply_to_message
        if replied.forward_from:
            target_id = replied.forward_from.id
        elif replied.from_user:
            target_id = replied.from_user.id

    if context.args and context.args[0].isdigit():
        target_id = int(context.args[0])

    if not target_id:
        await update.effective_message.reply_text("ℹ️ <b>Usage:</b> <code>/unban &lt;user_id&gt;</code>", parse_mode="HTML")
        return

    success = await set_user_ban_status(target_id, is_banned=False)
    if success:
        await update.effective_message.reply_text(f"✅ User <code>{target_id}</code> has been unbanned.", parse_mode="HTML")
    else:
        await update.effective_message.reply_text(f"⚠️ User <code>{target_id}</code> not found in database.", parse_mode="HTML")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /stats command."""
    if not update.effective_user or not update.effective_message:
        return

    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.effective_message.reply_text("⛔ You are not authorized to view admin statistics.")
        return

    stats = await get_admin_stats()
    
    platforms_text = ""
    if stats["platform_stats"]:
        for plat, count in stats["platform_stats"].items():
            platforms_text += f"  • <b>{plat.capitalize()}:</b> {count}\n"
    else:
        platforms_text = "  <i>No data available.</i>\n"

    text = (
        "<b>📈 Bot Global Statistics</b>\n\n"
        f"👥 <b>Total Users:</b> {stats['total_users']}\n"
        f"🟢 <b>Active (Last 24h):</b> {stats['active_24h']}\n"
        f"🚫 <b>Banned Users:</b> {stats['banned_users']}\n\n"
        f"✅ <b>Successful Downloads:</b> {stats['successful_downloads']}\n"
        f"❌ <b>Failed Downloads:</b> {stats['failed_downloads']}\n"
        f"💾 <b>Total Bandwidth Processed:</b> {format_size(stats['total_bytes'])}\n\n"
        f"<b>📊 Downloads by Platform:</b>\n{platforms_text}"
    )
    await update.effective_message.reply_text(text, parse_mode="HTML")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcasts a message to all users."""
    if not update.effective_user or not update.effective_message:
        return

    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "ℹ️ <b>Usage:</b> <code>/broadcast &lt;your message here&gt;</code>",
            parse_mode="HTML"
        )
        return

    broadcast_text = " ".join(context.args)
    user_ids = await get_all_user_ids()
    total = len(user_ids)

    if total == 0:
        await update.effective_message.reply_text("No users to broadcast to.")
        return

    progress_msg = await update.effective_message.reply_text(
        f"📢 <b>Starting Broadcast...</b>\nSending to {total} users.",
        parse_mode="HTML"
    )

    success_count = 0
    failed_count = 0

    for idx, target_id in enumerate(user_ids, 1):
        try:
            sent = await context.bot.send_message(
                chat_id=target_id,
                text=f"📢 <b>Announcement:</b>\n\n{safe_html(broadcast_text)}",
                parse_mode="HTML"
            )
            # Track broadcast message for 24h auto-deletion
            await track_message(target_id, sent.message_id, target_id)
            success_count += 1
        except TelegramError:
            failed_count += 1

        # Rate limit protection: sleep briefly
        await asyncio.sleep(0.05)

        if idx % 20 == 0 or idx == total:
            try:
                await progress_msg.edit_text(
                    f"📢 <b>Broadcasting:</b> {idx}/{total}\n"
                    f"✅ Success: {success_count} | ❌ Failed: {failed_count}",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    await progress_msg.edit_text(
        f"✅ <b>Broadcast Completed!</b>\n\n"
        f"👥 Total Target: {total}\n"
        f"✅ Delivered: {success_count}\n"
        f"❌ Failed: {failed_count}",
        parse_mode="HTML"
    )

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /ban <user_id>."""
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        return

    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("ℹ️ <b>Usage:</b> <code>/ban &lt;user_id&gt;</code>", parse_mode="HTML")
        return

    target_id = int(context.args[0])
    success = await set_user_ban_status(target_id, is_banned=True)
    if success:
        await update.effective_message.reply_text(f"🚫 User <code>{target_id}</code> has been banned.", parse_mode="HTML")
    else:
        await update.effective_message.reply_text(f"⚠️ User <code>{target_id}</code> not found in database.", parse_mode="HTML")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /unban <user_id>."""
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        return

    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("ℹ️ <b>Usage:</b> <code>/unban &lt;user_id&gt;</code>", parse_mode="HTML")
        return

    target_id = int(context.args[0])
    success = await set_user_ban_status(target_id, is_banned=False)
    if success:
        await update.effective_message.reply_text(f"✅ User <code>{target_id}</code> has been unbanned.", parse_mode="HTML")
    else:
        await update.effective_message.reply_text(f"⚠️ User <code>{target_id}</code> not found in database.", parse_mode="HTML")

async def manual_cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /cleanup command to manually trigger message & disk cleanup."""
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        return

    msg = await update.effective_message.reply_text("🧹 <b>Running cleanup routine...</b>", parse_mode="HTML")
    await auto_delete_expired_messages_job(context)
    deleted_dirs = cleanup_orphaned_temp_files(max_age_seconds=0)
    await msg.edit_text(
        f"✅ <b>Cleanup Complete!</b>\n"
        f"• Expired messages purged.\n"
        f"• Cleaned {deleted_dirs} temporary download directories.",
        parse_mode="HTML"
    )

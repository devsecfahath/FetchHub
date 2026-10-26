import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import asyncio
import sys
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from bot.config import BOT_TOKEN, CLEANUP_INTERVAL_MINUTES
from bot.database.db import init_db
from bot.services.cleaner import auto_delete_expired_messages_job, cleanup_orphaned_temp_files
from bot.handlers.start import start_command, help_command, about_command, mystats_command
from bot.handlers.media import handle_url_message
from bot.handlers.callbacks import handle_callback_query
from bot.handlers.admin import (
    admin_panel,
    stats_command,
    broadcast_command,
    ban_command,
    unban_command,
    manual_cleanup_command,
    users_list_command,
    find_user_command
)
from bot.utils.logger import logger

import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Media Downloader Bot is Running Healthy!")

    def log_message(self, format, *args):
        pass

def start_health_server():
    """Starts a minimal HTTP health server if PORT environment variable is set."""
    port_str = os.getenv("PORT")
    if port_str and port_str.isdigit():
        port = int(port_str)
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        logger.info("Health server listening on port %d (Free Web Service mode enabled)", port)

def main():
    """Main entry point to initialize and start the Telegram Media Downloader Bot."""
    start_health_server()
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is missing! Please set BOT_TOKEN in your .env file.")
        sys.exit(1)

    logger.info("Initializing database...")
    asyncio.run(init_db())

    # Startup cleanup of any dangling temp files from previous sessions
    cleanup_orphaned_temp_files(max_age_seconds=0)

    logger.info("Building Telegram Application...")
    from telegram.request import HTTPXRequest
    request_config = HTTPXRequest(
        connection_pool_size=32,
        read_timeout=300.0,
        write_timeout=300.0,
        connect_timeout=60.0,
        pool_timeout=60.0
    )
    app = ApplicationBuilder().token(BOT_TOKEN).request(request_config).build()

    # User commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("mystats", mystats_command))
    app.add_handler(CommandHandler("send", handle_url_message))

    # Admin commands
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("users", users_list_command))
    app.add_handler(CommandHandler("find", find_user_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("cleanup", manual_cleanup_command))

    # Callback queries (inline buttons)
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # General text message handler for automatic URL detection
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_url_message))

    # Scheduled background job: 24h Chat Message Auto-Cleaner
    if app.job_queue:
        app.job_queue.run_repeating(
            auto_delete_expired_messages_job,
            interval=CLEANUP_INTERVAL_MINUTES * 60,
            first=10,
            name="auto_delete_24h_cleaner"
        )
        logger.info("Scheduled 24h Auto-Delete cleaner to run every %d minutes.", CLEANUP_INTERVAL_MINUTES)
    else:
        logger.warning("JobQueue not available. Auto-delete scheduler disabled.")

    logger.info("Starting bot polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

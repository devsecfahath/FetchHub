import aiosqlite
from bot.config import DATABASE_PATH
from bot.utils.logger import logger

async def init_db():
    """Initializes SQLite database with necessary tables and indices."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_banned INTEGER DEFAULT 0,
                total_downloads INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                platform TEXT,
                file_type TEXT,
                file_size INTEGER DEFAULT 0,
                status TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS message_tracker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                user_id INTEGER,
                delete_at INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indices for high performance
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tracker_delete ON message_tracker(delete_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_downloads_user ON downloads(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_downloads_platform ON downloads(platform)")

        await db.commit()
    logger.info("Database initialized successfully at %s", DATABASE_PATH)

def get_db():
    """Returns an aiosqlite connection context manager."""
    return aiosqlite.connect(DATABASE_PATH)

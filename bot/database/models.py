import time
from typing import Optional, List, Dict, Any
import aiosqlite
from bot.database.db import get_db
from bot.config import AUTO_DELETE_HOURS

async def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
    """Inserts a new user or updates their username/last_active."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, last_active)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_active = CURRENT_TIMESTAMP
        """, (user_id, username, first_name))
        await db.commit()

async def is_user_banned(user_id: int) -> bool:
    """Checks if a user is banned."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row["is_banned"]:
                return True
            return False

async def set_user_ban_status(user_id: int, is_banned: bool) -> bool:
    """Bans or unbans a user."""
    async with get_db() as db:
        cursor = await db.execute("""
            UPDATE users SET is_banned = ? WHERE user_id = ?
        """, (1 if is_banned else 0, user_id))
        await db.commit()
        return cursor.rowcount > 0

async def log_download(
    user_id: int,
    url: str,
    platform: str,
    file_type: str,
    file_size: int = 0,
    status: str = "success",
    error_message: Optional[str] = None
) -> None:
    """Logs a media download attempt and increments user total downloads."""
    async with get_db() as db:
        await db.execute("""
            INSERT INTO downloads (user_id, url, platform, file_type, file_size, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, url, platform, file_type, file_size, status, error_message))

        if status == "success":
            await db.execute("""
                UPDATE users SET total_downloads = total_downloads + 1 WHERE user_id = ?
            """, (user_id,))

        await db.commit()

async def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Retrieves statistics for a single user."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT total_downloads, created_at, last_active FROM users WHERE user_id = ?
        """, (user_id,)) as cursor:
            user_row = await cursor.fetchone()

        async with db.execute("""
            SELECT platform, COUNT(*) as count FROM downloads
            WHERE user_id = ? AND status = 'success'
            GROUP BY platform
        """, (user_id,)) as cursor:
            platform_rows = await cursor.fetchall()

        platforms = {row["platform"]: row["count"] for row in platform_rows}
        
        return {
            "total_downloads": user_row["total_downloads"] if user_row else 0,
            "created_at": user_row["created_at"] if user_row else "N/A",
            "last_active": user_row["last_active"] if user_row else "N/A",
            "platform_breakdown": platforms
        }

async def get_admin_stats() -> Dict[str, Any]:
    """Retrieves global bot statistics for admin dashboard."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT COUNT(*) as count FROM users") as cursor:
            total_users = (await cursor.fetchone())["count"]

        async with db.execute("SELECT COUNT(*) as count FROM users WHERE is_banned = 1") as cursor:
            banned_users = (await cursor.fetchone())["count"]

        async with db.execute("SELECT COUNT(*) as count FROM downloads WHERE status = 'success'") as cursor:
            successful_downloads = (await cursor.fetchone())["count"]

        async with db.execute("SELECT COUNT(*) as count FROM downloads WHERE status = 'failed'") as cursor:
            failed_downloads = (await cursor.fetchone())["count"]

        async with db.execute("SELECT SUM(file_size) as total_bytes FROM downloads WHERE status = 'success'") as cursor:
            total_bytes = (await cursor.fetchone())["total_bytes"] or 0

        async with db.execute("""
            SELECT platform, COUNT(*) as count FROM downloads
            WHERE status = 'success'
            GROUP BY platform
            ORDER BY count DESC
        """) as cursor:
            platform_rows = await cursor.fetchall()

        platform_stats = {row["platform"]: row["count"] for row in platform_rows}

        # Active users in last 24 hours
        async with db.execute("""
            SELECT COUNT(*) as count FROM users
            WHERE datetime(last_active) >= datetime('now', '-1 day')
        """) as cursor:
            active_24h = (await cursor.fetchone())["count"]

        return {
            "total_users": total_users,
            "banned_users": banned_users,
            "active_24h": active_24h,
            "successful_downloads": successful_downloads,
            "failed_downloads": failed_downloads,
            "total_bytes": total_bytes,
            "platform_stats": platform_stats
        }

async def get_all_user_ids() -> List[int]:
    """Returns all non-banned user IDs for broadcasting."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id FROM users WHERE is_banned = 0") as cursor:
            rows = await cursor.fetchall()
            return [row["user_id"] for row in rows]

async def get_recent_users(limit: int = 25) -> List[Dict[str, Any]]:
    """Returns the most recently active users with their IDs and stats."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, username, first_name, is_banned, total_downloads, last_active
            FROM users
            ORDER BY last_active DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def search_users(query: str) -> List[Dict[str, Any]]:
    """Searches users by ID, username, or name."""
    clean_query = query.strip().lstrip("@")
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        if clean_query.isdigit():
            sql = "SELECT * FROM users WHERE user_id = ?"
            params = (int(clean_query),)
        else:
            sql = "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ? LIMIT 10"
            params = (f"%{clean_query}%", f"%{clean_query}%")

        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

# --- Message Tracking for 24h Auto-Cleanup ---

async def track_message(
    chat_id: int,
    message_id: int,
    user_id: Optional[int] = None,
    delete_after_seconds: Optional[int] = None
) -> None:
    """Records a message to be automatically deleted after expiration."""
    if delete_after_seconds is None:
        delete_after_seconds = AUTO_DELETE_HOURS * 3600

    delete_at = int(time.time()) + delete_after_seconds

    async with get_db() as db:
        await db.execute("""
            INSERT INTO message_tracker (chat_id, message_id, user_id, delete_at)
            VALUES (?, ?, ?, ?)
        """, (chat_id, message_id, user_id, delete_at))
        await db.commit()

async def get_expired_messages(current_timestamp: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetches messages whose deletion time has arrived."""
    if current_timestamp is None:
        current_timestamp = int(time.time())

    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT id, chat_id, message_id, user_id FROM message_tracker
            WHERE delete_at <= ?
            LIMIT 200
        """, (current_timestamp,)) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "chat_id": row["chat_id"],
                    "message_id": row["message_id"],
                    "user_id": row["user_id"]
                }
                for row in rows
            ]

async def delete_tracked_records(record_ids: List[int]) -> None:
    """Removes processed tracker records from DB."""
    if not record_ids:
        return
    placeholders = ",".join("?" * len(record_ids))
    async with get_db() as db:
        await db.execute(f"DELETE FROM message_tracker WHERE id IN ({placeholders})", record_ids)
        await db.commit()

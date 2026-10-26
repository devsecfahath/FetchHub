import asyncio
import os
import unittest
from pathlib import Path

from bot.services.url_detector import detect_platform, extract_urls, inspect_url
from bot.services.rate_limiter import RateLimiter
from bot.utils.helpers import format_size, format_duration, sanitize_filename
from bot.database.db import init_db
from bot.database.models import (
    upsert_user,
    is_user_banned,
    set_user_ban_status,
    log_download,
    get_user_stats,
    get_admin_stats,
    track_message,
    get_expired_messages,
    delete_tracked_records
)

class TestMediaDownloaderBot(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Initialize SQLite tables
        await init_db()

    def test_url_detector(self):
        """Tests URL extraction and platform classification."""
        sample_urls = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ": "youtube",
            "https://youtu.be/dQw4w9WgXcQ": "youtube",
            "https://www.youtube.com/shorts/abcd1234efg": "youtube",
            "https://www.instagram.com/reel/C1234567890/": "instagram",
            "https://www.instagram.com/p/C1234567890/": "instagram",
            "https://www.tiktok.com/@username/video/1234567890123456789": "tiktok",
            "https://vm.tiktok.com/ZM8abc123/": "tiktok",
            "https://www.facebook.com/watch/?v=123456789": "facebook",
            "https://fb.watch/abcd123/": "facebook",
            "https://twitter.com/user/status/1234567890123456789": "twitter",
            "https://x.com/user/status/1234567890123456789": "twitter",
            "https://reddit.com/r/videos/comments/abc/cool_clip/": "generic"
        }

        for url, expected_platform in sample_urls.items():
            platform, _ = detect_platform(url)
            self.assertEqual(platform, expected_platform, f"Failed detecting {url}")

        text_block = "Check this video https://youtu.be/test and this reel https://instagram.com/reel/123 ok!"
        extracted = extract_urls(text_block)
        self.assertEqual(len(extracted), 2)

    def test_helpers(self):
        """Tests helper formatters."""
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(1024 * 1024 * 15.5), "15.5 MB")
        self.assertEqual(format_duration(65), "01:05")
        self.assertEqual(format_duration(3665), "01:01:05")
        self.assertEqual(sanitize_filename("test/file:name*?.mp4"), "testfilename.mp4")

    def test_rate_limiter(self):
        """Tests user rate limiter."""
        limiter = RateLimiter(max_requests=2, window_seconds=10)
        user_id = 99999

        limited, _ = limiter.is_rate_limited(user_id)
        self.assertFalse(limited)

        limited, _ = limiter.is_rate_limited(user_id)
        self.assertFalse(limited)

        # 3rd request should be blocked
        limited, wait = limiter.is_rate_limited(user_id)
        self.assertTrue(limited)
        self.assertGreater(wait, 0)

    async def test_database_and_message_tracker(self):
        """Tests DB models, download logs, and 24h message tracking."""
        import random
        test_uid = random.randint(1000000, 9999999)
        await upsert_user(test_uid, f"tester_{test_uid}", "Test User")

        self.assertFalse(await is_user_banned(test_uid))
        await set_user_ban_status(test_uid, is_banned=True)
        self.assertTrue(await is_user_banned(test_uid))
        await set_user_ban_status(test_uid, is_banned=False)

        await log_download(
            user_id=test_uid,
            url="https://youtube.com/watch?v=123",
            platform="youtube",
            file_type="video",
            file_size=1024000,
            status="success"
        )

        user_stats = await get_user_stats(test_uid)
        self.assertEqual(user_stats["total_downloads"], 1)

        admin_stats = await get_admin_stats()
        self.assertGreaterEqual(admin_stats["total_users"], 1)
        self.assertGreaterEqual(admin_stats["successful_downloads"], 1)

        # Test message tracking and expiry (expire immediately for test)
        await track_message(chat_id=12345, message_id=5555, user_id=test_uid, delete_after_seconds=-10)
        expired = await get_expired_messages()
        found = [e for e in expired if e["message_id"] == 5555]
        self.assertTrue(len(found) > 0)

        # Delete tracked record
        await delete_tracked_records([found[0]["id"]])
        expired_after = await get_expired_messages()
        self.assertFalse(any(e["message_id"] == 5555 for e in expired_after))

if __name__ == "__main__":
    unittest.main()

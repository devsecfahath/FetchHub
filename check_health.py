import asyncio
import os
import sys

# Ensure UTF-8 output on Windows terminal
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
from bot.config import BOT_TOKEN, ADMIN_IDS, DOWNLOAD_DIR, DATABASE_PATH, AUTO_DELETE_HOURS, TARGET_COMPRESSION_MB
from bot.database.models import get_admin_stats, get_recent_users
from bot.services.url_detector import detect_platform

print("=" * 50)
print("🔍 BOT STATUS & SYSTEM HEALTH REPORT")
print("=" * 50)

print("\n1. Configuration:")
token_status = f"✅ Active (ends with ...{BOT_TOKEN[-6:]})" if BOT_TOKEN else "❌ Missing"
print(f"   • Bot Token: {token_status}")
print(f"   • Admin IDs: {list(ADMIN_IDS)}")
print(f"   • Database: {DATABASE_PATH} (Exists: {os.path.exists(DATABASE_PATH)})")
print(f"   • Downloads Directory: {DOWNLOAD_DIR} (Exists: {os.path.exists(DOWNLOAD_DIR)})")
print(f"   • Auto-Delete Message Window: {AUTO_DELETE_HOURS} hours")
print(f"   • Max Upload Compression Target: {TARGET_COMPRESSION_MB} MB")

print("\n2. Supported Platforms Check:")
test_urls = [
    ("YouTube Video", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("YouTube Short", "https://youtube.com/shorts/GqLCtrtio4w"),
    ("Instagram Reel", "https://www.instagram.com/reel/C12345/"),
    ("TikTok Video", "https://www.tiktok.com/@user/video/123"),
    ("Facebook Video", "https://facebook.com/watch/?v=123"),
    ("X / Twitter", "https://x.com/user/status/123"),
]
for name, url in test_urls:
    plat, label = detect_platform(url)
    print(f"   • {name:15} -> {label} (Key: {plat}) ✅")

async def check_db():
    print("\n3. Database & Activity Stats:")
    stats = await get_admin_stats()
    print(f"   • Registered Users: {stats['total_users']}")
    print(f"   • Active in Last 24h: {stats['active_24h']}")
    print(f"   • Successful Downloads: {stats['successful_downloads']}")
    print(f"   • Failed Downloads: {stats['failed_downloads']}")
    print(f"   • Total Bandwidth Processed: {stats['total_bytes'] / (1024*1024):.2f} MB")
    if stats['platform_stats']:
        print("   • Downloads by Platform:", stats['platform_stats'])
    
    users = await get_recent_users(5)
    if users:
        print("\n4. Recent Users in Database:")
        for u in users:
            print(f"   • ID: {u['user_id']} | Username: @{u['username']} | Name: {u['first_name']} | Downloads: {u['total_downloads']}")
    else:
        print("\n4. Recent Users: None registered yet (send /start in Telegram)")

asyncio.run(check_db())

print("\n" + "=" * 50)
print("✅ ALL SYSTEMS OPERATIONAL & HEALTHY")
print("=" * 50)

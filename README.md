<div align="center">

<img src="assets/images/mediafetchbot-banner.png" alt="MediaFetch Bot — download videos and audio from supported platforms" width="100%">

<h1>📥 MediaFetch Bot</h1>
<p>A powerful, open-source Telegram bot to download videos and audio from YouTube, Instagram, TikTok, Facebook, X (Twitter) and more — with smart FFmpeg compression and auto 24-hour chat cleanup.</p>

[![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)](https://python.org)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v20+-green?style=flat-square&logo=telegram)](https://python-telegram-bot.org)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-orange?style=flat-square)](https://github.com/yt-dlp/yt-dlp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-red?style=flat-square)](https://github.com/DevSecFahath/media-downloader-bot)

</div>

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔴 **YouTube** | Videos, Shorts, Playlists, MP3 audio |
| 📸 **Instagram** | Reels, Posts, Stories, IGTV |
| 🎵 **TikTok** | Watermark-free video downloads |
| 🔵 **Facebook** | Public videos and Reels |
| 🐦 **X (Twitter)** | HD videos and GIFs |
| 🌐 **Web Media** | Reddit, Pinterest, Threads + 1000+ sites via yt-dlp |
| ✂️ **Smart Compression** | FFmpeg auto-compresses to stay under Telegram's 50MB limit |
| 🧹 **24h Auto-Cleanup** | Messages auto-deleted after 24 hours for privacy |
| ⏱️ **Rate Limiting** | Per-user sliding window to prevent abuse |
| 👑 **Admin Panel** | Broadcast, ban/unban, stats, manual cleanup |
| 🔒 **Privacy First** | No messages or files are stored permanently |

---

## 📁 Project Structure

```
media-downloader-bot/
├── assets/images/              # README and repository artwork
├── bot/
│   ├── config.py               # Environment config, limits, paths
│   ├── database/
│   │   ├── db.py               # SQLite async connection & schema
│   │   └── models.py           # DB operations: users, logs, tracker
│   ├── handlers/
│   │   ├── start.py            # /start, /help, /about, /mystats
│   │   ├── media.py            # URL detection & format selection
│   │   ├── callbacks.py        # Download pipeline & inline buttons
│   │   └── admin.py            # Admin commands
│   ├── services/
│   │   ├── downloader.py       # yt-dlp wrapper (download + metadata)
│   │   ├── processor.py        # FFmpeg compression & MP3 conversion
│   │   ├── url_detector.py     # Platform detection & URL cleaning
│   │   ├── rate_limiter.py     # Per-user rate limiter
│   │   └── cleaner.py          # 24h auto-delete worker
│   └── utils/
│       ├── progress.py         # Live Telegram progress updates
│       ├── helpers.py          # Formatters & sanitizers
│       └── logger.py           # Structured logging
├── tests/                      # Unit tests
├── .env.example                # Configuration template
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker container definition
├── render.yaml                 # Render.com deploy blueprint
└── run.py                      # Bot entry point
```

---

## 🚀 Quick Start

### Prerequisites
- Python **3.10+** (3.12 recommended)
- **FFmpeg** installed and on your system PATH ([download here](https://ffmpeg.org/download.html))
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### 1. Clone the Repository
```bash
git clone https://github.com/DevSecFahath/media-downloader-bot.git
cd media-downloader-bot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
```
Edit `.env` with your values:
```env
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=your_telegram_user_id
```

### 4. Run the Bot
```bash
python run.py
```

---

## ☁️ Hosting Options

> **Note for Instagram/TikTok:** Cloud datacenter IPs (Render, AWS) may be rate-limited by Instagram.
> For best compatibility, run the bot on a **home PC or personal VPS**.
> Alternatively, add your Instagram cookies as `COOKIES_TEXT` environment variable (see below).

### 🏠 Option 1: Run Locally (Best Compatibility)
```bash
python run.py
```

Keep it running 24/7 with [PM2](https://pm2.keymetrics.io/):
```bash
npm install -g pm2
pm2 start run.py --interpreter python --name mediafetch
pm2 save && pm2 startup
```

### ☁️ Option 2: Render.com (Free Web Service)
1. Fork this repository to your GitHub.
2. Sign up at [render.com](https://render.com).
3. New → **Web Service** → Connect your repository.
4. Set environment variables: `BOT_TOKEN` and `ADMIN_IDS`.
5. Click **Deploy**.

### 🐋 Option 3: Docker
```bash
docker build -t mediafetch-bot .
docker run -d --name mediafetch --restart always --env-file .env mediafetch-bot
```

### 🌩️ Option 4: Oracle Cloud Always Free (Best Free VPS)
1. Create account at [cloud.oracle.com](https://cloud.oracle.com) (free, no charges)
2. Launch an Ubuntu Always Free ARM VM
3. Deploy with Docker or run directly with Python

---

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | — | Telegram bot token from @BotFather |
| `ADMIN_IDS` | ✅ | — | Comma-separated Telegram user IDs for admin access |
| `DOWNLOAD_DIR` | ❌ | `downloads` | Temporary download directory |
| `DATABASE_PATH` | ❌ | `bot.db` | SQLite database path |
| `MAX_CONCURRENT_DOWNLOADS` | ❌ | `3` | Max parallel downloads |
| `RATE_LIMIT_PER_MINUTE` | ❌ | `5` | Max requests per user per minute |
| `AUTO_DELETE_HOURS` | ❌ | `24` | Hours before messages are auto-deleted |
| `CLEANUP_INTERVAL_MINUTES` | ❌ | `15` | How often the auto-delete worker runs |
| `COOKIES_TEXT` | ❌ | — | Netscape-format cookies for Instagram/YouTube cloud bypass |

---

## 🤖 Commands

### User Commands
| Command | Description |
|---|---|
| `/start` | Launch the bot and view main menu |
| `/send <URL>` | Download media from a URL directly |
| `/mystats` | View your download history |
| `/help` | Usage guide |
| `/about` | About the bot and privacy notice |

### Admin Commands
| Command | Description |
|---|---|
| `/admin` | Admin control panel |
| `/stats` | Global bot statistics |
| `/users` | List recent users |
| `/broadcast <message>` | Send announcement to all users |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/find <user_id>` | Look up a user by ID |
| `/cleanup` | Manually trigger 24h cleanup |

---

## 🍪 Instagram Note

Instagram (Meta) rate-limits anonymous requests from cloud datacenter IPs. To enable Instagram downloads when hosted on cloud services:

1. Install **[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)** browser extension
2. Open [Instagram.com](https://instagram.com) while logged in
3. Click the extension → **Export** cookies
4. Add the cookie text as `COOKIES_TEXT` environment variable in your hosting platform

> Best alternative: run the bot on a home PC or personal VPS (Oracle Cloud free tier).

---

## 🛠️ Development

### Run Tests
```bash
python -m unittest discover tests
```

### Tech Stack
- **[python-telegram-bot](https://python-telegram-bot.org/)** v20+ — Async Telegram API wrapper
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — Powerful media extraction engine (1000+ sites)
- **[FFmpeg](https://ffmpeg.org/)** — Video compression, MP3 conversion, thumbnail generation
- **[aiosqlite](https://github.com/omnilib/aiosqlite)** — Async SQLite for user tracking & logs
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** — Environment variable management

---

## 🤝 Contributing

Contributions are very welcome! Here is how:

1. **Fork** the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit: `git commit -m "Add your feature"`
4. Push: `git push origin feature/your-feature`
5. Open a **Pull Request**

Please ensure tests pass: `python -m unittest discover tests`

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## ⭐ Support

If this project helped you, please give it a ⭐ on GitHub — it helps others find it!

---

<div align="center">
Made with ❤️ by <a href="https://github.com/Fahath0x">Fahath0x</a>
</div>

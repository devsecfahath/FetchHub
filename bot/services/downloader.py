import asyncio
import os
import random
import uuid
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any, List
import yt_dlp

# Realistic mobile user agents to rotate for social media platforms
_MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/125.0.0.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
]

from bot.config import DOWNLOAD_DIR, MAX_CONCURRENT_DOWNLOADS, COOKIES_FILE_PATH
from bot.services.processor import FFmpegProcessor
from bot.utils.logger import logger
from bot.utils.helpers import sanitize_filename

# Global semaphore to limit concurrent heavy media downloads
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

@dataclass
class MediaInfo:
    title: str
    duration: int
    uploader: str
    thumbnail_url: Optional[str]
    platform: str
    views: Optional[int]
    is_playlist: bool
    entries_count: int

@dataclass
class DownloadResult:
    file_path: Path
    temp_dir: Path
    title: str
    duration: int
    thumbnail_path: Optional[Path]
    file_size: int
    file_type: str  # "video" or "audio"
    width: Optional[int]
    height: Optional[int]
    was_compressed: bool = False

    def cleanup(self) -> None:
        """Deletes the temporary directory containing all downloaded and processed files."""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.debug("Cleaned up temp directory: %s", self.temp_dir)
        except Exception as e:
            logger.warning("Error cleaning up temp directory %s: %s", self.temp_dir, e)

class MediaDownloader:
    """Wrapper around yt-dlp with optimized settings for multi-platform media downloading."""

    @staticmethod
    def _get_base_ydl_opts(mobile: bool = False) -> Dict[str, Any]:
        """Returns robust base options for yt-dlp, optimized for cloud & datacenter servers."""
        ua = random.choice(_MOBILE_USER_AGENTS) if mobile else (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "geo_bypass": True,
            "extract_flat": False,
            "socket_timeout": 60,
            "windowsfilenames": True,
            "restrictfilenames": True,
            "retries": 3,
            "fragment_retries": 3,
            "sleep_interval": 2,
            "max_sleep_interval": 5,
            "http_headers": {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Mode": "navigate",
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "android", "tv", "mweb", "web_creator"],
                    "player_skip": ["webpage", "configs", "js"],
                },
                "youtubetab": {
                    "skip": ["authcheck"],
                },
            },
        }
        if COOKIES_FILE_PATH:
            opts["cookiefile"] = COOKIES_FILE_PATH
        return opts

    @classmethod
    async def extract_media_info(cls, url: str) -> Optional[MediaInfo]:
        """Extracts media metadata without downloading."""
        def _extract():
            opts = cls._get_base_ydl_opts()
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=False)
            except Exception as first_err:
                logger.warning("Primary info extraction failed: %s. Retrying with relaxed options...", first_err)
                # Fallback relaxed options
                fallback_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "nocheckcertificate": True,
                    "ignoreerrors": True,
                    "geo_bypass": True,
                }
                with yt_dlp.YoutubeDL(fallback_opts) as fallback_ydl:
                    return fallback_ydl.extract_info(url, download=False)

        try:
            loop = asyncio.get_running_loop()
            info = await loop.run_in_executor(None, _extract)
            if not info:
                return None

            # Handle playlists or single entry
            if "entries" in info:
                entries = [e for e in info.get("entries", []) if e]
                first_entry = entries[0] if entries else {}
                return MediaInfo(
                    title=info.get("title") or first_entry.get("title", "Untitled Playlist"),
                    duration=first_entry.get("duration", 0) if first_entry else 0,
                    uploader=info.get("uploader") or (first_entry.get("uploader") if first_entry else "Unknown"),
                    thumbnail_url=first_entry.get("thumbnail") if first_entry else None,
                    platform=info.get("extractor_key", "generic"),
                    views=first_entry.get("view_count") if first_entry else None,
                    is_playlist=True,
                    entries_count=len(entries)
                )

            return MediaInfo(
                title=info.get("title", "Untitled Media"),
                duration=int(info.get("duration") or 0),
                uploader=info.get("uploader") or info.get("channel") or info.get("creator") or "Unknown",
                thumbnail_url=info.get("thumbnail"),
                platform=info.get("extractor_key", "generic"),
                views=info.get("view_count"),
                is_playlist=False,
                entries_count=1
            )
        except Exception as e:
            logger.error("Failed to extract info for URL %s: %s", url, e)
            return None

    @classmethod
    async def download(
        cls,
        url: str,
        format_type: str = "video",
        progress_hook: Optional[Callable[[dict], None]] = None
    ) -> DownloadResult:
        """
        Downloads media (video or audio) using yt-dlp and processes with FFmpeg.
        Runs under a concurrency semaphore to protect system memory/CPU.
        """
        async with download_semaphore:
            job_id = str(uuid.uuid4())
            temp_dir = DOWNLOAD_DIR / job_id
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Constant safe template eliminating all possible invalid character/length filesystem errors
            out_template = str(temp_dir / "video.%(ext)s")

            opts = cls._get_base_ydl_opts()
            opts["outtmpl"] = out_template

            if progress_hook:
                opts["progress_hooks"] = [progress_hook]

            if format_type == "audio":
                # Best audio extraction -> mp3
                opts["format"] = "bestaudio/best"
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            else:
                # Video format: Prioritize MP4 (h264 + aac) for native Telegram preview
                opts["format"] = (
                    "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best"
                )
                opts["merge_output_format"] = "mp4"

            def _run_ydl(use_mobile_ua: bool = False):
                dl_opts = cls._get_base_ydl_opts(mobile=use_mobile_ua)
                dl_opts["outtmpl"] = out_template
                dl_opts["progress_hooks"] = opts.get("progress_hooks", [])
                for k in ("format", "postprocessors", "merge_output_format"):
                    if k in opts:
                        dl_opts[k] = opts[k]
                with yt_dlp.YoutubeDL(dl_opts) as ydl:
                    return ydl.extract_info(url, download=True)

            loop = asyncio.get_running_loop()
            try:
                info = await loop.run_in_executor(None, lambda: _run_ydl(use_mobile_ua=False))
            except Exception as first_err:
                err_str = str(first_err)
                # Retry once with a randomized mobile User-Agent for social media 429s
                if "429" in err_str or "Too Many Requests" in err_str or "rate" in err_str.lower():
                    logger.warning("Got 429 from platform, retrying with mobile UA in 4s...")
                    await asyncio.sleep(4)
                    try:
                        info = await loop.run_in_executor(None, lambda: _run_ydl(use_mobile_ua=True))
                    except Exception as retry_err:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        retry_str = str(retry_err)
                        if "429" in retry_str or "Too Many Requests" in retry_str:
                            raise RuntimeError(
                                "Instagram/platform is blocking cloud server requests (HTTP 429).\n"
                                "📌 Fix: Add your Instagram cookies in Render Environment Variables as COOKIES_TEXT."
                            )
                        raise RuntimeError(f"Download failed: {retry_str}")
                else:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise RuntimeError(f"Download failed: {err_str}")

            if not info:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise RuntimeError("No media found at the provided URL.")

            # Find the downloaded file in temp_dir
            downloaded_files = [f for f in temp_dir.glob("*.*") if not f.name.endswith(".part")]
            if not downloaded_files:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise RuntimeError("Downloaded media file was not found on disk.")

            primary_file = downloaded_files[0]
            title = info.get("title") or "Media File"
            duration = int(info.get("duration") or 0)
            was_compressed = False

            thumb_path = None
            width = None
            height = None

            if format_type == "video":
                # Probe video info
                probe = await FFmpegProcessor.get_media_info(primary_file)
                duration = probe.get("duration", duration)
                width = probe.get("width")
                height = probe.get("height")

                # Generate thumbnail
                candidate_thumb = temp_dir / "thumbnail.jpg"
                thumb_path = await FFmpegProcessor.generate_thumbnail(primary_file, candidate_thumb)

                # Check if video exceeds 50MB and auto-compress
                compressed_target = temp_dir / "compressed_video.mp4"
                compressed_file, did_compress = await FFmpegProcessor.compress_video(
                    primary_file, compressed_target
                )
                if did_compress:
                    primary_file = compressed_file
                    was_compressed = True

            elif format_type == "audio":
                # Ensure it has .mp3 extension if converted
                mp3_files = list(temp_dir.glob("*.mp3"))
                if mp3_files:
                    primary_file = mp3_files[0]

            file_size = os.path.getsize(primary_file)

            return DownloadResult(
                file_path=primary_file,
                temp_dir=temp_dir,
                title=title,
                duration=duration,
                thumbnail_path=thumb_path,
                file_size=file_size,
                file_type=format_type,
                width=width,
                height=height,
                was_compressed=was_compressed
            )

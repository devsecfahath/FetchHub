import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from bot.config import TARGET_COMPRESSION_MB
from bot.utils.logger import logger

class FFmpegProcessor:
    """Handles video compression, audio conversion, thumbnail generation, and metadata probing."""

    @staticmethod
    async def get_media_info(file_path: Path) -> Dict[str, Any]:
        """Probes media file using ffprobe to get duration, width, height, bitrate."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                logger.error("ffprobe error: %s", stderr.decode())
                return {}

            data = json.loads(stdout.decode())
            info = {
                "duration": 0,
                "width": None,
                "height": None,
                "bitrate": 0,
                "has_video": False,
                "has_audio": False
            }

            if "format" in data:
                info["duration"] = int(float(data["format"].get("duration", 0)))
                info["bitrate"] = int(data["format"].get("bit_rate", 0))

            for stream in data.get("streams", []):
                codec_type = stream.get("codec_type")
                if codec_type == "video" and not info["has_video"]:
                    info["has_video"] = True
                    info["width"] = int(stream.get("width", 0))
                    info["height"] = int(stream.get("height", 0))
                elif codec_type == "audio":
                    info["has_audio"] = True

            return info
        except Exception as e:
            logger.error("Failed to probe media info: %s", e)
            return {}

    @staticmethod
    async def generate_thumbnail(video_path: Path, output_thumb_path: Path) -> Optional[Path]:
        """Generates a JPEG thumbnail at 1s of the video."""
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", "00:00:01",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(output_thumb_path)
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            if process.returncode == 0 and output_thumb_path.exists():
                return output_thumb_path
            logger.warning("Thumbnail generation warning: %s", stderr.decode())
            return None
        except Exception as e:
            logger.error("Failed to generate thumbnail: %s", e)
            return None

    @staticmethod
    async def convert_to_mp3(input_path: Path, output_path: Path) -> Optional[Path]:
        """Converts any audio/video input to high quality MP3 (192kbps)."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-vn",
            "-acodec", "libmp3lame",
            "-b:a", "192k",
            str(output_path)
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            if process.returncode == 0 and output_path.exists():
                return output_path
            logger.error("MP3 conversion failed: %s", stderr.decode())
            return None
        except Exception as e:
            logger.error("Error converting to MP3: %s", e)
            return None

    @staticmethod
    async def compress_video(
        input_path: Path,
        output_path: Path,
        target_size_mb: float = TARGET_COMPRESSION_MB
    ) -> Tuple[Optional[Path], bool]:
        """
        Compresses video to fit within target_size_mb using smart dynamic bitrate calculation.
        Returns (compressed_file_path, was_compressed).
        """
        file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        if file_size_mb <= target_size_mb:
            return input_path, False

        info = await FFmpegProcessor.get_media_info(input_path)
        duration = info.get("duration", 0)

        if duration <= 0:
            # Fallback duration probe if format duration was missing
            duration = 60

        # Calculate target bitrate
        # Total bits = target_size_mb * 8 * 1024 * 1024
        # Total kbps = (target_size_mb * 8192) / duration
        total_bitrate_kbps = (target_size_mb * 8192) / duration
        audio_bitrate_kbps = 128 if total_bitrate_kbps > 256 else 64
        video_bitrate_kbps = max(100, int(total_bitrate_kbps - audio_bitrate_kbps))

        logger.info(
            "Compressing video '%s' (%.2f MB) -> target %.2f MB (Duration: %ss, Video: %skbps, Audio: %skbps)",
            input_path.name, file_size_mb, target_size_mb, duration, video_bitrate_kbps, audio_bitrate_kbps
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-c:v", "libx264",
            "-b:v", f"{video_bitrate_kbps}k",
            "-maxrate", f"{int(video_bitrate_kbps * 1.4)}k",
            "-bufsize", f"{int(video_bitrate_kbps * 2)}k",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", f"{audio_bitrate_kbps}k",
            "-movflags", "+faststart",
            str(output_path)
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            if process.returncode == 0 and output_path.exists():
                compressed_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                logger.info("Compression complete: %.2f MB", compressed_size_mb)
                return output_path, True
            
            logger.error("FFmpeg compression failed: %s", stderr.decode())
            return input_path, False
        except Exception as e:
            logger.error("Exception during video compression: %s", e)
            return input_path, False

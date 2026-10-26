import asyncio
import os
import unittest
from pathlib import Path

from bot.services.processor import FFmpegProcessor
from bot.services.downloader import MediaDownloader

class TestProcessorAndDownloader(unittest.IsolatedAsyncioTestCase):

    async def test_ffmpeg_probe_and_compression_calc(self):
        """Tests that FFmpegProcessor correctly initializes and handles invalid files safely."""
        fake_path = Path("fake_video_123.mp4")
        info = await FFmpegProcessor.get_media_info(fake_path)
        self.assertEqual(info, {})

        thumb = await FFmpegProcessor.generate_thumbnail(fake_path, Path("thumb.jpg"))
        self.assertIsNone(thumb)

        mp3 = await FFmpegProcessor.convert_to_mp3(fake_path, Path("out.mp3"))
        self.assertIsNone(mp3)

    def test_downloader_options(self):
        """Tests downloader base options."""
        opts = MediaDownloader._get_base_ydl_opts()
        self.assertTrue(opts["quiet"])
        self.assertTrue(opts["geo_bypass"])
        self.assertIn("Mozilla", opts["http_headers"]["User-Agent"])

if __name__ == "__main__":
    unittest.main()

"""Tests for the yt-dlp engine wrapper."""
from unittest.mock import patch, MagicMock
from src.core.engine import VideoEngine
from src.core.models import DownloadStatus


class TestFetchMetadata:
    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_fetch_basic(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "webpage_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "duration": 212,
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
            "channel": "TestChannel",
            "upload_date": "20240101",
            "view_count": 1000000,
            "formats": [
                {
                    "format_id": "137",
                    "ext": "mp4",
                    "resolution": "1920x1080",
                    "fps": 30,
                    "vcodec": "avc1",
                    "acodec": "none",
                    "filesize": 50_000_000,
                    "tbr": 2500,
                },
            ],
            "subtitles": {"en": [{"ext": "vtt", "name": "English"}]},
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        engine = VideoEngine()
        result = engine.fetch_metadata("https://youtube.com/watch?v=dQw4w9WgXcQ")

        assert result["video"].id == "dQw4w9WgXcQ"
        assert result["video"].title == "Test Video"
        assert result["video"].duration == 212
        assert result["video"].channel == "TestChannel"
        assert len(result["video_formats"]) == 1
        assert result["video_formats"][0].format_id == "137"
        assert result["video_formats"][0].resolution_short == "1080p"
        assert result["video_formats"][0].has_video is True
        assert result["video_formats"][0].has_audio is False
        assert len(result["audio_formats"]) == 0
        assert len(result["combined_formats"]) == 0
        assert len(result["subtitles"]) == 1
        assert result["subtitles"][0].language == "en"

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_fetch_separates_audio_formats(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "id": "test",
            "title": "Test",
            "duration": 100,
            "formats": [
                {
                    "format_id": "140",
                    "ext": "m4a",
                    "acodec": "mp4a",
                    "vcodec": "none",
                    "abr": 128,
                    "tbr": 128,
                    "filesize": 1_000_000,
                },
                {
                    "format_id": "137",
                    "ext": "mp4",
                    "vcodec": "avc1",
                    "acodec": "none",
                    "resolution": "1920x1080",
                    "fps": 30,
                    "filesize": 50_000_000,
                },
                {
                    "format_id": "22",
                    "ext": "mp4",
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "resolution": "1280x720",
                    "fps": 30,
                    "filesize": 10_000_000,
                },
            ],
            "subtitles": {},
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        engine = VideoEngine()
        result = engine.fetch_metadata("https://youtube.com/watch?v=test")

        assert len(result["audio_formats"]) == 1
        assert result["audio_formats"][0].format_id == "140"
        assert len(result["video_formats"]) == 1
        assert result["video_formats"][0].format_id == "137"
        assert len(result["combined_formats"]) == 1
        assert result["combined_formats"][0].format_id == "22"

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_fetch_sorts_by_resolution(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "id": "test",
            "title": "Test",
            "duration": 100,
            "formats": [
                {"format_id": "1", "ext": "mp4", "resolution": "640x360",
                 "vcodec": "h264", "acodec": "none"},
                {"format_id": "2", "ext": "mp4", "resolution": "1920x1080",
                 "vcodec": "h264", "acodec": "none"},
                {"format_id": "3", "ext": "mp4", "resolution": "1280x720",
                 "vcodec": "h264", "acodec": "none"},
            ],
            "subtitles": {},
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        engine = VideoEngine()
        result = engine.fetch_metadata("url")

        formats = result["video_formats"]
        assert formats[0].format_id == "2"  # 1080p first
        assert formats[1].format_id == "3"  # 720p second
        assert formats[2].format_id == "1"  # 360p last


class TestProgressHook:
    def test_progress_callback_receives_updates(self):
        callback_data = []

        def callback(progress):
            callback_data.append(progress)

        engine = VideoEngine(progress_callback=callback)

        # Simulate downloading hook
        engine._progress_hook({
            "status": "downloading",
            "downloaded_bytes": 5_000_000,
            "total_bytes": 10_000_000,
            "_speed_str": "2.0 MiB/s",
            "_eta_str": "5s",
            "_downloaded_bytes_str": "5.0 MiB",
            "_total_bytes_str": "10.0 MiB",
            "filename": "test.mp4",
        })

        assert len(callback_data) == 1
        assert callback_data[0].status == DownloadStatus.DOWNLOADING
        assert callback_data[0].percent == 50.0
        assert callback_data[0].speed == "2.0 MiB/s"

    def test_progress_callback_finished(self):
        callback_data = []

        engine = VideoEngine(progress_callback=lambda p: callback_data.append(p))
        engine._progress_hook({"status": "finished"})

        assert len(callback_data) == 1
        assert callback_data[0].status == DownloadStatus.PROCESSING
        assert callback_data[0].percent == 100.0

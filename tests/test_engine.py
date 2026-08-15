"""Tests for the yt-dlp engine wrapper."""
from unittest.mock import patch, MagicMock
import tempfile
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

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_fetch_parses_automatic_captions(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "id": "test", "title": "Test", "duration": 10,
            "formats": [], "subtitles": {},
            "automatic_captions": {
                "en": [{"ext": "vtt"}], "tr": [{"ext": "srv3"}],
            },
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        result = VideoEngine().fetch_metadata("url")

        assert [track.language for track in result["automatic_captions"]] == ["en", "tr"]
        assert result["automatic_captions"][0].is_auto is True

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_download_passes_audio_subtitle_and_transcript_options(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        track = type("Track", (), {"language": "tr", "is_auto": True})()

        result = VideoEngine().download(
            "url", tempfile.gettempdir(), "137", audio_format_id="140",
            subtitle_lang="en", text_track=track, merge_output_format="mp4",
        )

        assert result == 0
        opts = mock_ydl_cls.call_args.args[0]
        assert opts["format"] == "137+140"
        assert opts["writesubtitles"] is True
        assert opts["writeautomaticsub"] is True
        assert opts["subtitleslangs"] == ["en"]
        assert opts["merge_output_format"] == "mp4"

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_download_can_write_automatic_caption_track_when_selected(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        track = type("Track", (), {"language": "tr", "is_auto": True})()

        result = VideoEngine().download(
            "url", tempfile.gettempdir(), "137", text_track=track,
        )

        assert result == 0
        opts = mock_ydl_cls.call_args.args[0]
        assert opts["writeautomaticsub"] is True
        assert opts["subtitleslangs"] == ["tr"]

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_download_can_write_manual_subtitle_track_selected_as_text_asset(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        track = type("Track", (), {"language": "en", "is_auto": False})()

        result = VideoEngine().download(
            "url", tempfile.gettempdir(), "137", text_track=track,
        )

        assert result == 0
        opts = mock_ydl_cls.call_args.args[0]
        assert opts["writesubtitles"] is True
        assert opts["writeautomaticsub"] is False
        assert opts["subtitleslangs"] == ["en"]

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_download_disables_playlist_expansion(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        assert VideoEngine().download("url", tempfile.gettempdir(), "137") == 0
        assert mock_ydl_cls.call_args.args[0]["noplaylist"] is True

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_failed_download_preserves_last_error(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.download.side_effect = RuntimeError("HTTP Error 503: Service Unavailable")
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        engine = VideoEngine()
        assert engine.download("url", tempfile.gettempdir(), "137") == 1
        assert "503" in engine.last_download_error


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


class TestDownloadRetry:
    @patch("src.core.engine.time.sleep")
    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_transient_first_attempt_is_retried_before_auth_strategies(self, mock_ydl_cls, mock_sleep):
        attempts = []
        ydl = MagicMock()

        def download(_urls):
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("transient network failure")

        ydl.download.side_effect = download
        mock_ydl_cls.return_value.__enter__.return_value = ydl

        result = VideoEngine().download(
            "https://example.com/video", tempfile.gettempdir(), "137"
        )

        assert result == 0
        assert len(attempts) == 2
        mock_sleep.assert_called_once()


class TestFetchHangPrevention:
    """Fetch must never hang on playlist URLs or stalled connections."""

    def test_base_opts_prevent_hangs(self):
        opts = VideoEngine()._base_opts()
        assert opts["socket_timeout"] == 15
        assert opts["noplaylist"] is True

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_fetch_passes_hang_prevention_opts(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "id": "x", "title": "T", "duration": 1,
            "formats": [], "subtitles": {},
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        VideoEngine().fetch_metadata("https://youtube.com/watch?v=x")

        opts = mock_ydl_cls.call_args.args[0]
        assert opts["noplaylist"] is True
        assert opts["socket_timeout"] == 15

    def test_browser_cookie_strategies_come_last(self):
        labels = [s["label"] for s in VideoEngine()._get_strategies()]
        assert labels[0] == "no-auth"
        assert labels[-1] == "edge"
        assert labels[-2] == "chrome"
        assert labels.index("chrome") > labels.index("no-auth")

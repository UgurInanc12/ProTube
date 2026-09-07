"""Tests for audio-only and subtitle-only download modes."""
import tempfile
from unittest.mock import MagicMock, patch

from src.core.download_options import (
    DOWNLOAD_MODE_AUDIO,
    DOWNLOAD_MODE_TEXT,
    DOWNLOAD_MODE_VIDEO,
    resolve_best_audio_format_id,
)
from src.core.engine import VideoEngine
from src.core.models import FormatInfo, TextTrackInfo


def audio_format(format_id, abr, ext, codec, filesize=None, note=""):
    return FormatInfo(
        format_id=format_id,
        ext=ext,
        resolution="",
        fps=None,
        codec=codec,
        filesize=filesize,
        abr=abr,
        format_note=note,
        has_video=False,
        has_audio=True,
    )


class TestBestAudioSelection:
    def test_best_audio_picks_the_highest_bitrate_track(self):
        formats = [
            audio_format("249", 47.0, "webm", "opus"),
            audio_format("140", 129.5, "m4a", "mp4a.40.2"),
            audio_format("251", 104.9, "webm", "opus"),
        ]

        assert resolve_best_audio_format_id(formats) == "140"

    def test_best_audio_prefers_the_unprocessed_track_over_drc(self):
        """DRC tracks are dynamic-range compressed, not the original audio."""
        formats = [
            audio_format("140-drc", 129.472, "m4a", "mp4a.40.2", note="medium, DRC"),
            audio_format("140", 129.472, "m4a", "mp4a.40.2", note="medium"),
        ]

        assert resolve_best_audio_format_id(formats) == "140"

    def test_best_audio_returns_none_without_audio_tracks(self):
        assert resolve_best_audio_format_id([]) is None

    def test_drc_penalty_outranks_a_larger_drc_filesize(self):
        """The DRC variant is often the bigger file at an identical bitrate."""
        formats = [
            audio_format("140-drc", 129.472, "m4a", "mp4a.40.2",
                         filesize=3450102, note="medium, DRC"),
            audio_format("140", 129.472, "m4a", "mp4a.40.2",
                         filesize=3449215, note="medium"),
        ]

        assert resolve_best_audio_format_id(formats) == "140"


class TestAudioOnlyDownload:
    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_audio_only_download_requests_just_the_audio_format(self, mock_ydl_cls):
        mock_ydl_cls.return_value.__enter__.return_value = MagicMock()

        result = VideoEngine().download(
            "url", tempfile.gettempdir(), format_id=None,
            audio_format_id="140", download_mode=DOWNLOAD_MODE_AUDIO,
        )

        assert result == 0
        opts = mock_ydl_cls.call_args.args[0]
        assert opts["format"] == "140"
        assert opts.get("skip_download") is not True

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_audio_only_download_does_not_force_a_video_container(self, mock_ydl_cls):
        """Remuxing an m4a into mp4 would re-container audio for no reason."""
        mock_ydl_cls.return_value.__enter__.return_value = MagicMock()

        VideoEngine().download(
            "url", tempfile.gettempdir(), format_id=None,
            audio_format_id="140", download_mode=DOWNLOAD_MODE_AUDIO,
            merge_output_format="mp4",
        )

        assert "merge_output_format" not in mock_ydl_cls.call_args.args[0]

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_audio_only_download_can_still_write_a_subtitle_sidecar(self, mock_ydl_cls):
        mock_ydl_cls.return_value.__enter__.return_value = MagicMock()

        VideoEngine().download(
            "url", tempfile.gettempdir(), format_id=None,
            audio_format_id="251", download_mode=DOWNLOAD_MODE_AUDIO,
            subtitle_lang="en",
        )

        opts = mock_ydl_cls.call_args.args[0]
        assert opts["format"] == "251"
        assert opts["writesubtitles"] is True
        assert opts["subtitleslangs"] == ["en"]


class TestTextOnlyDownload:
    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_text_only_download_skips_the_media_stream(self, mock_ydl_cls):
        mock_ydl_cls.return_value.__enter__.return_value = MagicMock()

        result = VideoEngine().download(
            "url", tempfile.gettempdir(), format_id=None,
            download_mode=DOWNLOAD_MODE_TEXT, subtitle_lang="en",
        )

        assert result == 0
        opts = mock_ydl_cls.call_args.args[0]
        assert opts["skip_download"] is True
        assert opts["writesubtitles"] is True
        assert opts["subtitleslangs"] == ["en"]
        assert "format" not in opts

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_text_only_download_can_fetch_an_automatic_transcript(self, mock_ydl_cls):
        mock_ydl_cls.return_value.__enter__.return_value = MagicMock()

        track = TextTrackInfo("tr", "Turkish", "vtt", is_auto=True)
        VideoEngine().download(
            "url", tempfile.gettempdir(), format_id=None,
            download_mode=DOWNLOAD_MODE_TEXT, text_track=track,
        )

        opts = mock_ydl_cls.call_args.args[0]
        assert opts["skip_download"] is True
        assert opts["writeautomaticsub"] is True
        assert opts["subtitleslangs"] == ["tr"]

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_video_mode_still_downloads_media(self, mock_ydl_cls):
        mock_ydl_cls.return_value.__enter__.return_value = MagicMock()

        VideoEngine().download(
            "url", tempfile.gettempdir(), "137", audio_format_id="140",
            download_mode=DOWNLOAD_MODE_VIDEO, merge_output_format="mp4",
        )

        opts = mock_ydl_cls.call_args.args[0]
        assert opts["format"] == "137+140"
        assert opts.get("skip_download") is not True
        assert opts["merge_output_format"] == "mp4"


class TestAudioCodecLabel:
    def test_audio_only_format_reports_its_audio_codec(self):
        """YouTube sends vcodec='none' for audio tracks: a truthy string."""
        fmt = VideoEngine._fmt({
            "format_id": "140",
            "ext": "m4a",
            "vcodec": "none",
            "acodec": "mp4a.40.2",
            "abr": 129.5,
        })

        assert fmt.has_video is False
        assert fmt.has_audio is True
        assert fmt.codec == "mp4a.40.2"

    def test_video_only_format_still_reports_its_video_codec(self):
        fmt = VideoEngine._fmt({
            "format_id": "137",
            "ext": "mp4",
            "vcodec": "avc1.640028",
            "acodec": "none",
            "resolution": "1920x1080",
        })

        assert fmt.codec == "avc1.640028"


class TestTranscriptOrdering:
    """YouTube returns one real ASR track plus ~150 machine translations of it."""

    ASR_URL = "https://www.youtube.com/api/timedtext?v=X&kind=asr&lang=en&fmt=json3"
    TRANSLATED_URL = ASR_URL + "&tlang=ab"

    def tracks(self):
        # Alphabetical order, exactly as yt-dlp hands it over: 'ab' comes first.
        return {
            "ab": [{"ext": "vtt", "url": self.TRANSLATED_URL}],
            "en": [{"ext": "vtt", "url": self.ASR_URL}],
            "tr": [{"ext": "vtt", "url": self.ASR_URL + "&tlang=tr"}],
        }

    def test_the_spoken_language_is_offered_before_translations(self):
        result = VideoEngine()._parse_text_tracks(self.tracks())

        assert result[0].language == "en"
        assert [t.language for t in result[1:]] == ["ab", "tr"]

    def test_translations_are_marked_as_translations(self):
        by_lang = {t.language: t for t in VideoEngine()._parse_text_tracks(self.tracks())}

        assert by_lang["en"].is_translation is False
        assert by_lang["ab"].is_translation is True
        assert "auto-translated" in by_lang["ab"].label
        assert "auto-translated" not in by_lang["en"].label

    def test_no_transcripts_yields_no_tracks(self):
        assert VideoEngine()._parse_text_tracks({}) == []


class TestDownloadStrategyFallback:
    """Browser-cookie strategies must not mask a non-auth failure."""

    @patch("src.core.engine.time.sleep")
    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_rate_limit_reports_itself_not_a_cookie_error(self, mock_ydl_cls, _sleep):
        # no-auth raises 429 twice (initial + transient retry), then the cookie
        # strategies would raise their own unrelated error if they were reached.
        errors = [
            Exception("HTTP Error 429: Too Many Requests"),
            Exception("HTTP Error 429: Too Many Requests"),
            Exception("Could not copy Chrome cookie database"),
            Exception("Could not copy Chrome cookie database"),
        ]
        mock_ydl_cls.return_value.__enter__.return_value.download.side_effect = errors

        engine = VideoEngine()
        result = engine.download("url", tempfile.gettempdir(), "137")

        assert result == 1
        assert "429" in engine.last_download_error
        assert "cookie" not in engine.last_download_error.lower()

    @patch("src.core.engine.yt_dlp.YoutubeDL")
    def test_auth_failure_still_falls_through_to_cookies(self, mock_ydl_cls):
        ydl = mock_ydl_cls.return_value.__enter__.return_value
        ydl.download.side_effect = [Exception("Sign in to confirm your age"), None]

        result = VideoEngine().download("url", tempfile.gettempdir(), "137")

        assert result == 0
        assert ydl.download.call_count == 2

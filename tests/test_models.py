"""Tests for data models."""
import pytest
from src.core.models import (
    VideoInfo, FormatInfo, SubtitleInfo,
    DownloadProgress, DownloadStatus, SessionState,
)


class TestVideoInfo:
    def test_creation(self):
        info = VideoInfo(
            id="dQw4w9WgXcQ",
            title="Test Video",
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            duration=212,
        )
        assert info.id == "dQw4w9WgXcQ"
        assert info.title == "Test Video"

    def test_duration_formatted_minutes(self):
        info = VideoInfo(id="x", title="T", url="u", duration=212)
        assert info.duration_formatted == "3:32"

    def test_duration_formatted_hours(self):
        info = VideoInfo(id="x", title="T", url="u", duration=3725)
        assert info.duration_formatted == "1:02:05"

    def test_duration_formatted_zero(self):
        info = VideoInfo(id="x", title="T", url="u", duration=0)
        assert info.duration_formatted == "0:00"


class TestFormatInfo:
    def test_resolution_short(self):
        fmt = FormatInfo(format_id="137", ext="mp4", resolution="1920x1080")
        assert fmt.resolution_short == "1080p"

    def test_resolution_short_720p(self):
        fmt = FormatInfo(format_id="22", ext="mp4", resolution="1280x720")
        assert fmt.resolution_short == "720p"

    def test_resolution_short_empty(self):
        fmt = FormatInfo(format_id="140", ext="m4a", resolution="")
        assert fmt.resolution_short == ""

    def test_filesize_mb(self):
        fmt = FormatInfo(format_id="137", ext="mp4", filesize=50_000_000)
        assert fmt.filesize_mb == pytest.approx(47.68, rel=0.01)

    def test_filesize_mb_none(self):
        fmt = FormatInfo(format_id="137", ext="mp4", filesize=None)
        assert fmt.filesize_mb is None

    def test_quality_label(self):
        fmt = FormatInfo(
            format_id="137", ext="mp4", resolution="1920x1080",
            fps=30, codec="avc1",
        )
        assert "1080p" in fmt.quality_label
        assert "AVC1" in fmt.quality_label

    def test_quality_label_60fps(self):
        fmt = FormatInfo(
            format_id="299", ext="mp4", resolution="1920x1080",
            fps=60, codec="avc1",
        )
        assert "1080p" in fmt.quality_label
        assert "60fps" in fmt.quality_label


class TestSubtitleInfo:
    def test_label_regular(self):
        sub = SubtitleInfo(language="en", language_name="English")
        assert sub.label == "English"

    def test_label_auto(self):
        sub = SubtitleInfo(language="en", language_name="English", is_auto=True)
        assert sub.label == "English (auto)"

    def test_label_fallback(self):
        sub = SubtitleInfo(language="xx")
        assert sub.label == "xx"


class TestDownloadProgress:
    def test_defaults(self):
        progress = DownloadProgress()
        assert progress.status == DownloadStatus.PENDING
        assert progress.percent == 0.0
        assert progress.speed == ""

    def test_custom(self):
        progress = DownloadProgress(
            status=DownloadStatus.DOWNLOADING,
            percent=45.5,
            speed="2.5 MiB/s",
            eta="30s",
        )
        assert progress.percent == 45.5
        assert progress.speed == "2.5 MiB/s"


class TestSessionState:
    def test_creation(self):
        video = VideoInfo(id="x", title="T", url="u", duration=10)
        session = SessionState(video=video)
        assert session.video is video
        assert session.formats == []
        assert session.download_progress.status == DownloadStatus.PENDING

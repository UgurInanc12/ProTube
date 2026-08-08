"""Data models for ProTube."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DownloadStatus(Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class VideoInfo:
    """Metadata about a YouTube video."""

    id: str
    title: str
    url: str
    duration: int  # seconds
    thumbnail_url: str = ""
    channel: str = ""
    channel_url: str = ""
    upload_date: str = ""
    description: str = ""
    view_count: int = 0

    @property
    def duration_formatted(self) -> str:
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


@dataclass
class FormatInfo:
    """Represents a single downloadable format (video-only, audio-only, or combined)."""

    format_id: str
    ext: str
    resolution: str = ""  # e.g. "1920x1080"
    fps: Optional[float] = None
    codec: str = ""
    filesize: Optional[int] = None  # bytes
    tbr: Optional[float] = None  # total bitrate kbps
    vbr: Optional[float] = None  # video bitrate kbps
    abr: Optional[float] = None  # audio bitrate kbps
    format_note: str = ""  # e.g. "1080p", "720p60"
    has_video: bool = True
    has_audio: bool = True

    @property
    def resolution_short(self) -> str:
        if not self.resolution:
            return ""
        try:
            h = int(self.resolution.split("x")[1])
            return f"{h}p"
        except (IndexError, ValueError):
            return self.resolution

    @property
    def filesize_mb(self) -> Optional[float]:
        if self.filesize is None:
            return None
        return round(self.filesize / (1024 * 1024), 2)

    @property
    def quality_label(self) -> str:
        parts = [self.resolution_short] if self.resolution_short else []
        if self.fps and self.fps > 30:
            parts.append(f"{int(self.fps)}fps")
        if self.codec:
            parts.append(self.codec.upper())
        return " ".join(parts) or self.format_id


@dataclass
class SubtitleInfo:
    """Represents available subtitle track."""

    language: str
    language_name: str = ""
    ext: str = "vtt"
    is_auto: bool = False

    @property
    def label(self) -> str:
        name = self.language_name or self.language
        suffix = " (auto)" if self.is_auto else ""
        return f"{name}{suffix}"


@dataclass
class DownloadProgress:
    """Track download progress for a single file."""

    status: DownloadStatus = DownloadStatus.PENDING
    percent: float = 0.0
    speed: str = ""
    eta: str = ""
    downloaded: str = ""
    total: str = ""
    filename: str = ""


@dataclass
class SessionState:
    """Represents a single video session."""

    video: VideoInfo
    formats: list[FormatInfo] = field(default_factory=list)
    subtitles: list[SubtitleInfo] = field(default_factory=list)
    selected_video_format: Optional[str] = None
    selected_audio_format: Optional[str] = None
    selected_subtitle: Optional[str] = None
    download_progress: DownloadProgress = field(default_factory=DownloadProgress)
    post_processing_queue: list[str] = field(default_factory=list)

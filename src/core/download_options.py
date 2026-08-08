"""Pure helpers for resolving download assets from UI selections."""
from typing import Iterable, Optional

from src.core.models import FormatInfo


def _audio_matches_video_container(video: FormatInfo, audio: FormatInfo) -> bool:
    """Return whether an audio format can be merged into the video container."""
    video_ext = (video.ext or "").lower()
    audio_ext = (audio.ext or "").lower()
    codec = (audio.codec or "").lower()
    if video_ext == "webm":
        return audio_ext == "webm" or "opus" in codec or "vorbis" in codec
    if video_ext == "mp4":
        return audio_ext in {"m4a", "mp4"} or "mp4a" in codec or "aac" in codec
    return audio_ext == video_ext


def resolve_audio_format_id(
    video_format: FormatInfo,
    audio_mode: str,
    selected_audio_id: Optional[str],
    audio_formats: Iterable[FormatInfo],
) -> Optional[str]:
    """Resolve the audio stream to pair with a selected video format.

    Video formats that already contain audio never receive a second stream.
    Video-only formats default to the highest-quality compatible audio stream
    unless the user explicitly chooses no audio or a particular stream.
    """
    if video_format.has_audio or audio_mode == "included":
        return None
    if audio_mode == "none":
        return None

    available = list(audio_formats)
    if audio_mode == "format" and selected_audio_id:
        return selected_audio_id

    compatible = [
        audio for audio in available
        if _audio_matches_video_container(video_format, audio)
    ]
    best = compatible[0] if compatible else (available[0] if available else None)
    return best.format_id if best else None


def audio_format_by_id(
    formats: Iterable[FormatInfo], format_id: Optional[str]
) -> Optional[FormatInfo]:
    """Find an audio format by its yt-dlp format ID."""
    if not format_id:
        return None
    return next((fmt for fmt in formats if fmt.format_id == format_id), None)


def resolve_merge_format(
    video_format: FormatInfo, audio_format: Optional[FormatInfo]
) -> str:
    """Choose a container that can hold the selected video and audio streams."""
    video_ext = (video_format.ext or "mp4").lower()
    if not audio_format or video_format.has_audio:
        return video_ext
    return video_ext if _audio_matches_video_container(video_format, audio_format) else "mkv"


def video_format_by_id(
    formats: Iterable[FormatInfo], format_id: str
) -> Optional[FormatInfo]:
    """Find the selected video format without coupling the GUI to list ordering."""
    return next((fmt for fmt in formats if fmt.format_id == format_id), None)


__all__ = [
    "audio_format_by_id",
    "resolve_audio_format_id",
    "resolve_merge_format",
    "video_format_by_id",
]

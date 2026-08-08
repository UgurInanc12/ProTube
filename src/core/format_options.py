"""Compact grouping and presentation helpers for video format choices."""
from dataclasses import dataclass
from typing import Iterable

from src.core.models import FormatInfo, TextTrackInfo


@dataclass(frozen=True)
class VideoFormatGroup:
    """Formats sharing one resolution and frame-rate combination."""

    key: str
    label: str
    formats: tuple[FormatInfo, ...]


def _height(fmt: FormatInfo) -> int:
    try:
        return int(fmt.resolution.split("x", 1)[1]) if fmt.resolution else 0
    except (IndexError, ValueError):
        return 0


def _fps_value(fmt: FormatInfo) -> float:
    return float(fmt.fps or 0)


def _group_key(fmt: FormatInfo) -> tuple[int, float]:
    return _height(fmt), _fps_value(fmt)


def group_video_formats(formats: Iterable[FormatInfo]) -> list[VideoFormatGroup]:
    """Group formats by resolution and FPS, highest quality first."""
    grouped: dict[tuple[int, float], list[FormatInfo]] = {}
    for fmt in formats:
        grouped.setdefault(_group_key(fmt), []).append(fmt)

    result = []
    for (height, fps), variants in sorted(grouped.items(), reverse=True):
        variants.sort(key=lambda item: (item.filesize or 0, item.format_id), reverse=True)
        fps_label = f"{int(fps)} fps" if fps.is_integer() else f"{fps:g} fps"
        resolution = f"{height}p" if height else "Unknown quality"
        key = f"{height}:{fps:g}"
        result.append(VideoFormatGroup(
            key=key,
            label=f"{resolution} · {fps_label}" if height and fps else resolution,
            formats=tuple(variants),
        ))
    return result


def codec_family(fmt: FormatInfo) -> str:
    """Return a short, user-facing codec family name."""
    codec = (fmt.codec or "").lower()
    if codec.startswith("av01") or "av1" in codec:
        return "AV1"
    if codec.startswith("vp09") or codec.startswith("vp9") or "vp9" in codec:
        return "VP9"
    if codec.startswith("avc1") or codec.startswith("avc") or "h264" in codec:
        return "H.264"
    if codec.startswith("hev") or "h265" in codec or "hevc" in codec:
        return "H.265"
    return (fmt.codec or "Unknown").upper()


def dynamic_range_label(fmt: FormatInfo) -> str:
    """Return a concise HDR badge label, or SDR for ordinary formats."""
    if not fmt.is_hdr:
        return "SDR"
    value = (fmt.dynamic_range or "").strip()
    if value and value.lower() not in {"hdr", "unknown"}:
        return value.upper()
    return "HDR"


def variant_label(fmt: FormatInfo) -> str:
    """Build the compact secondary line shown for one codec variant."""
    size = f"{fmt.filesize_mb:.1f} MB" if fmt.filesize_mb is not None else "size unknown"
    audio = "Audio + video" if fmt.has_audio else "Video only"
    return f"{codec_family(fmt)} · {dynamic_range_label(fmt)} · {fmt.ext.upper()} · {size} · {audio}"


def variant_options(formats: Iterable[FormatInfo]) -> list[tuple[str, FormatInfo]]:
    """Return unique display labels while retaining every underlying format."""
    used: dict[str, int] = {}
    result = []
    for fmt in formats:
        base = variant_label(fmt)
        used[base] = used.get(base, 0) + 1
        label = base if used[base] == 1 else f"{base} · Format {used[base]}"
        result.append((label, fmt))
    return result


def is_hdr_format(fmt: FormatInfo) -> bool:
    """Expose HDR state without requiring the GUI to inspect raw yt-dlp data."""
    return fmt.is_hdr


def text_track_options(
    subtitles: Iterable[TextTrackInfo],
    auto_captions: Iterable[TextTrackInfo],
) -> list[tuple[str, TextTrackInfo | None]]:
    """Build a compact text-track menu with an explicit no-track option."""
    options: list[tuple[str, TextTrackInfo | None]] = [("No subtitles or transcript", None)]
    options.extend((f"Subtitle: {track.label}", track) for track in subtitles)
    options.extend((f"Transcript: {track.label}", track) for track in auto_captions)
    return options


__all__ = [
    "VideoFormatGroup",
    "codec_family",
    "dynamic_range_label",
    "group_video_formats",
    "is_hdr_format",
    "text_track_options",
    "variant_label",
    "variant_options",
]

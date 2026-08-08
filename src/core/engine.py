"""yt-dlp engine wrapper for fetching metadata and downloading."""
import logging
import os
import sys
import shutil
from typing import Optional, Callable
import yt_dlp
from src.core.models import (
    VideoInfo, FormatInfo, SubtitleInfo,
    DownloadProgress, DownloadStatus,
)

log = logging.getLogger("protube")

# Find Node.js for yt-dlp JS runtime (YouTube requires it since 2025)
_NODE_PATH = shutil.which("node") or ""


class VideoEngine:
    """Wraps yt-dlp for metadata fetching and downloading.

    Tries every strategy in order, regardless of error type.
    """

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback

    def _base_opts(self) -> dict:
        opts = {"quiet": True, "no_warnings": True}
        if _NODE_PATH:
            opts["extractor_args"] = {
                "youtube": {"js_runtimes": [f"node:{_NODE_PATH}"]}
            }
        return opts

    # ── strategies ─────────────────────────────────────────────

    def _get_strategies(self) -> list[dict]:
        """All auth strategies, tried in order."""
        strategies = [
            {"label": "no-auth", "opts": {}},
            {"label": "chrome", "opts": {"cookiesfrombrowser": ["chrome"]}},
            {"label": "edge", "opts": {"cookiesfrombrowser": ["edge"]}},
        ]

        # cookies.txt file (user exports via Chrome extension)
        from src.core.session_manager import SessionManager
        cookies_txt = SessionManager().base_dir / "cookies.txt"
        if cookies_txt.exists():
            strategies.append({
                "label": "cookies.txt",
                "opts": {"cookies": str(cookies_txt)},
            })

        return strategies

    # ── fetch ──────────────────────────────────────────────────

    def fetch_metadata(self, url: str) -> dict:
        last_error = None
        for strategy in self._get_strategies():
            try:
                return self._try_fetch(url, strategy)
            except Exception as e:
                last_error = e
                log.warning(f"[{strategy['label']}] fetch failed: {str(e)[:150]}")

        # All failed - give clear instructions
        from src.core.session_manager import SessionManager
        cookies_path = SessionManager().base_dir / "cookies.txt"
        raise RuntimeError(
            f"YouTube requires sign-in for this video.\n\n"
            f"Quick fix (one-time, 30 seconds):\n"
            f"1. Open Chrome, go to youtube.com\n"
            f"2. Install extension: 'Get cookies.txt LOCALLY'\n"
            f"3. Click the extension icon on youtube.com\n"
            f"4. Click 'Export' → save as:\n"
            f"   {cookies_path}\n"
            f"5. Retry in ProTube - works immediately."
        )

    # ── download ───────────────────────────────────────────────

    def download(
        self,
        url: str,
        output_dir: str,
        format_id: str,
        audio_format_id: Optional[str] = None,
        subtitle_lang: Optional[str] = None,
        embed_subs: bool = False,
    ) -> int:
        format_str = format_id
        if audio_format_id:
            format_str = f"{format_id}+{audio_format_id}"

        output_template = f"{output_dir}/%(title)s.%(ext)s"

        base_opts = self._base_opts()
        base_opts.update({
            "format": format_str,
            "outtmpl": output_template,
            "progress_hooks": [self._progress_hook] if self.progress_callback else [],
            "writesubtitles": bool(subtitle_lang),
            "subtitleslangs": [subtitle_lang] if subtitle_lang else [],
            "embedsubtitles": embed_subs,
            "merge_output_format": "mp4",
        })

        for strategy in self._get_strategies():
            try:
                opts = dict(base_opts)
                opts.update(strategy["opts"])
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                log.info(f"Download OK [{strategy['label']}]")
                if self.progress_callback:
                    self.progress_callback(
                        DownloadProgress(status=DownloadStatus.COMPLETED, percent=100.0)
                    )
                return 0
            except Exception as e:
                log.warning(f"[{strategy['label']}] download failed: {str(e)[:150]}")

        if self.progress_callback:
            self.progress_callback(DownloadProgress(status=DownloadStatus.FAILED))
        return 1

    # ── internals ──────────────────────────────────────────────

    def _try_fetch(self, url: str, strategy: dict) -> dict:
        opts = self._base_opts()
        opts["extract_flat"] = False
        opts.update(strategy["opts"])

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            "video": VideoInfo(
                id=info.get("id", ""),
                title=info.get("title", ""),
                url=info.get("webpage_url", url),
                duration=info.get("duration", 0) or 0,
                thumbnail_url=info.get("thumbnail", ""),
                channel=info.get("channel", "") or info.get("uploader", ""),
                channel_url=info.get("channel_url", ""),
                upload_date=info.get("upload_date", ""),
                description=(info.get("description", "") or "")[:500],
                view_count=info.get("view_count", 0) or 0,
            ),
            "video_formats": self._parse_video_formats(info.get("formats", [])),
            "audio_formats": self._parse_audio_formats(info.get("formats", [])),
            "combined_formats": self._parse_combined_formats(info.get("formats", [])),
            "subtitles": self._parse_subtitles(info.get("subtitles", {})),
            "raw": info,
        }

    def _progress_hook(self, d: dict):
        if not self.progress_callback:
            return
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            pct = (downloaded / total * 100) if total else 0
            self.progress_callback(DownloadProgress(
                status=DownloadStatus.DOWNLOADING, percent=pct,
                speed=d.get("_speed_str", ""), eta=d.get("_eta_str", ""),
                downloaded=d.get("_downloaded_bytes_str", ""),
                total=d.get("_total_bytes_str", ""),
                filename=d.get("filename", ""),
            ))
        elif d["status"] == "finished":
            self.progress_callback(
                DownloadProgress(status=DownloadStatus.PROCESSING, percent=100.0)
            )

    @staticmethod
    def _fmt(f: dict) -> FormatInfo:
        has_video = f.get("vcodec", "none") != "none"
        has_audio = f.get("acodec", "none") != "none"
        return FormatInfo(
            format_id=f.get("format_id", ""),
            ext=f.get("ext", ""),
            resolution=f.get("resolution", "") or "",
            fps=f.get("fps"),
            codec=(f.get("vcodec") or f.get("acodec") or ""),
            filesize=f.get("filesize"),
            tbr=f.get("tbr"), vbr=f.get("vbr"), abr=f.get("abr"),
            format_note=f.get("format_note", ""),
            has_video=has_video, has_audio=has_audio,
        )

    @staticmethod
    def _sort_formats(formats: list[FormatInfo]):
        def key(fmt):
            try:
                return int(fmt.resolution.split("x")[1]) if fmt.resolution else 0
            except (IndexError, ValueError):
                return 0
        formats.sort(key=key, reverse=True)

    def _parse_video_formats(self, raw: list) -> list[FormatInfo]:
        fmts = [self._fmt(f) for f in raw
                if f.get("vcodec", "none") != "none" and f.get("acodec", "none") == "none"]
        self._sort_formats(fmts)
        return fmts

    def _parse_audio_formats(self, raw: list) -> list[FormatInfo]:
        fmts = [self._fmt(f) for f in raw
                if f.get("acodec", "none") != "none" and f.get("vcodec", "none") == "none"]
        fmts.sort(key=lambda f: f.abr or 0, reverse=True)
        return fmts

    def _parse_combined_formats(self, raw: list) -> list[FormatInfo]:
        fmts = [self._fmt(f) for f in raw
                if f.get("vcodec", "none") != "none" and f.get("acodec", "none") != "none"]
        self._sort_formats(fmts)
        return fmts

    def _parse_subtitles(self, subtitles: dict) -> list[SubtitleInfo]:
        result = []
        lang_names = {
            "en": "English", "tr": "Turkish", "de": "German",
            "fr": "French", "es": "Spanish", "ja": "Japanese",
            "ko": "Korean", "ru": "Russian", "ar": "Arabic",
            "zh": "Chinese", "pt": "Portuguese", "it": "Italian",
        }
        for lang, tracks in subtitles.items():
            if tracks:
                ext = tracks[0].get("ext", "vtt")
                is_auto = any("auto" in t.get("name", "").lower() for t in tracks)
                result.append(SubtitleInfo(
                    language=lang,
                    language_name=lang_names.get(lang, lang.upper()),
                    ext=ext, is_auto=is_auto,
                ))
        return result

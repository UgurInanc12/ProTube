"""Session registry: tracks downloaded videos and provides file listing."""
import os
import sys
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

log = logging.getLogger("protube")


@dataclass
class SessionRecord:
    """Record of a downloaded video session."""
    video_id: str
    title: str
    url: str
    downloaded_file: str  # absolute path to the main video file
    download_date: str = ""
    subtitles_file: str = ""  # path to downloaded subtitle, if any
    video_format: str = ""  # format_id used
    audio_format: str = ""  # audio format_id used


class SessionManager:
    """Manages session persistence, discovery, and file organization."""

    SESSIONS_FOLDER_NAME = "ProTube Sessions"
    SESSIONS_JSON = "sessions.json"

    def __init__(self):
        self._base_dir = self._resolve_base_dir()
        self._sessions_file = self._base_dir / self.SESSIONS_JSON
        self._records: dict[str, SessionRecord] = {}  # keyed by session folder name
        self._load()

    # ── path resolution ──────────────────────────────────────────

    def _resolve_base_dir(self) -> Path:
        """Resolve the sessions directory.

        Priority:
        1. EXE mode: <exe_dir>/ProTube Sessions/
        2. Dev mode:  <project_root>/sessions/
        """
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).parent
            return exe_dir / self.SESSIONS_FOLDER_NAME

        # Dev mode: use project root (2 levels up from this file)
        this_file = Path(__file__).resolve()
        project_root = this_file.parent.parent.parent  # src/core -> src -> pro-tube
        return project_root / "sessions"

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def session_dir(self, folder_name: str) -> Path:
        return self._base_dir / folder_name

    # ── persistence ───────────────────────────────────────────────

    def _load(self):
        """Load session records from JSON."""
        log.debug(f"Loading sessions from: {self._sessions_file}")
        if self._sessions_file.exists():
            try:
                data = json.loads(self._sessions_file.read_text(encoding="utf-8"))
                for key, rec in data.items():
                    self._records[key] = SessionRecord(**rec)
                log.info(f"Loaded {len(self._records)} session(s) from disk")
            except (json.JSONDecodeError, TypeError) as e:
                log.error(f"Failed to parse sessions.json: {e}")
                self._records = {}
        else:
            log.debug("No sessions.json found, starting fresh")

    def _save(self):
        """Persist session records to JSON."""
        self._base_dir.mkdir(parents=True, exist_ok=True)
        data = {key: asdict(rec) for key, rec in self._records.items()}
        self._sessions_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log.debug(f"Saved {len(self._records)} session(s) to {self._sessions_file}")

    # ── session operations ────────────────────────────────────────

    def create_session(self, video_id: str, title: str, url: str) -> str:
        """Create a new session folder and return its name.

        Folder name is derived from the sanitized title.
        Duplicate titles get a #N suffix.
        """
        base = self._sanitize(title)
        folder_name = base
        counter = 2
        while (self._base_dir / folder_name).exists():
            folder_name = f"{base} #{counter}"
            counter += 1

        session_path = self._base_dir / folder_name
        session_path.mkdir(parents=True, exist_ok=True)

        return folder_name

    def record_download(self, folder_name: str, record: SessionRecord):
        """Record a completed download."""
        self._records[folder_name] = record
        log.info(f"Recorded download: '{folder_name}' -> {record.downloaded_file}")
        self._save()

    def get_record(self, folder_name: str) -> Optional[SessionRecord]:
        return self._records.get(folder_name)

    def list_sessions(self) -> list[dict]:
        """Return list of sessions with their metadata, newest first.

        Each dict: {folder_name, title, video_id, downloaded_file, download_date}
        """
        result = []
        for folder_name, rec in self._records.items():
            file_exists = os.path.exists(rec.downloaded_file)
            if not file_exists:
                log.warning(f"Session '{folder_name}' file missing: {rec.downloaded_file}")
            result.append({
                "folder_name": folder_name,
                "title": rec.title,
                "video_id": rec.video_id,
                "downloaded_file": rec.downloaded_file if file_exists else "",
                "download_date": rec.download_date,
                "subtitles_file": rec.subtitles_file,
            })
        # Newest first (by folder creation time)
        result.sort(
            key=lambda s: os.path.getctime(
                str(self._base_dir / s["folder_name"])
            ) if os.path.exists(str(self._base_dir / s["folder_name"])) else 0,
            reverse=True,
        )
        return result

    def get_display_title(self, folder_name: str) -> str:
        """Get human-friendly title for a session. Uses the #N format from folder name."""
        rec = self._records.get(folder_name)
        if rec:
            return rec.title
        return folder_name

    def get_output_path(self, folder_name: str, filename: str) -> str:
        """Get full path for a file in a session folder."""
        return str(self._base_dir / folder_name / filename)

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _sanitize(name: str) -> str:
        """Sanitize a string for use as a folder name."""
        # Remove or replace problematic characters
        result = []
        for ch in name:
            if ch.isalnum() or ch in " _-(),.":
                result.append(ch)
            else:
                result.append("_")
        sanitized = "".join(result).strip()
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip(". ")
        # Limit length
        if len(sanitized) > 80:
            sanitized = sanitized[:77] + "..."
        return sanitized or "untitled"

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Sanitize for use as a filename (more strict than folder)."""
        result = []
        for ch in name:
            if ch.isalnum() or ch in " _-.":
                result.append(ch)
            else:
                result.append("_")
        return "".join(result).strip()[:120] or "untitled"

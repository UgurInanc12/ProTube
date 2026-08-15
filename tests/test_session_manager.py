"""Tests for session folder lifecycle: failed downloads must not eat names."""
from src.core.session_manager import SessionManager, SessionRecord


def make_manager(tmp_path, monkeypatch) -> SessionManager:
    """SessionManager isolated into a temp base dir."""
    sm = SessionManager()
    monkeypatch.setattr(sm, "_base_dir", tmp_path)
    monkeypatch.setattr(sm, "_sessions_file", tmp_path / "sessions.json")
    return sm


def test_discard_session_removes_folder(tmp_path, monkeypatch):
    sm = make_manager(tmp_path, monkeypatch)
    folder = sm.create_session("vid1", "My Video", "http://x")
    assert (tmp_path / folder).exists()

    sm.discard_session(folder)

    assert not (tmp_path / folder).exists()


def test_discarded_name_is_reused_on_next_attempt(tmp_path, monkeypatch):
    """A failed attempt must not consume the '#2' suffix for the retry."""
    sm = make_manager(tmp_path, monkeypatch)
    first = sm.create_session("vid1", "My Video", "http://x")
    sm.discard_session(first)

    second = sm.create_session("vid1", "My Video", "http://x")

    assert second == first


def test_discard_session_removes_record(tmp_path, monkeypatch):
    sm = make_manager(tmp_path, monkeypatch)
    folder = sm.create_session("vid1", "My Video", "http://x")
    rec = SessionRecord(
        video_id="vid1", title="My Video", url="http://x",
        downloaded_file=str(tmp_path / folder / "x.mp4"),
    )
    sm.record_download(folder, rec)
    assert folder in sm._records

    sm.discard_session(folder)

    assert folder not in sm._records


def test_discard_unknown_folder_is_safe(tmp_path, monkeypatch):
    sm = make_manager(tmp_path, monkeypatch)

    sm.discard_session("does-not-exist")  # must not raise

from pathlib import Path

import build


def test_clean_preserves_dist_sessions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sessions = Path("dist") / "ProTube Sessions"
    sessions.mkdir(parents=True)
    subtitle = sessions / "video.en.srt"
    subtitle.write_text("subtitle", encoding="utf-8")
    Path("build").mkdir()
    Path("ProTube.spec").write_text("spec", encoding="utf-8")

    build.clean()

    assert subtitle.read_text(encoding="utf-8") == "subtitle"
    assert not Path("build").exists()
    assert not Path("ProTube.spec").exists()
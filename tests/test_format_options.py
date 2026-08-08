"""Tests for compact video format grouping and labels."""
from src.core.format_options import (
    codec_family,
    group_video_formats,
    variant_label,
    text_track_options,
    variant_options,
)
from src.core.models import FormatInfo, TextTrackInfo
from src.core.download_options import (
    resolve_audio_format_id,
    resolve_merge_format,
    video_format_by_id,
)


def make_format(
    format_id,
    resolution,
    fps,
    codec,
    ext,
    filesize,
    dynamic_range="",
    has_audio=False,
):
    return FormatInfo(
        format_id=format_id,
        ext=ext,
        resolution=resolution,
        fps=fps,
        codec=codec,
        filesize=filesize,
        dynamic_range=dynamic_range,
        has_video=True,
        has_audio=has_audio,
    )


def test_video_formats_group_by_resolution_and_fps():
    formats = [
        make_format("137", "1920x1080", 60, "avc1.64002A", "mp4", 94_000_000),
        make_format("248", "1920x1080", 60, "vp09.00.41.08", "webm", 67_000_000),
        make_format("399", "1920x1080", 30, "av01.0.09M.08", "mp4", 50_000_000),
        make_format("271", "2560x1440", 60, "vp09.00.50.08", "webm", 217_000_000),
    ]

    groups = group_video_formats(formats)

    assert [group.label for group in groups] == [
        "1440p · 60 fps",
        "1080p · 60 fps",
        "1080p · 30 fps",
    ]
    assert [fmt.format_id for fmt in groups[1].formats] == ["137", "248"]


def test_variant_label_makes_codec_and_hdr_choice_explicit():
    hdr = make_format(
        "400",
        "1920x1080",
        60,
        "av01.0.12M.08",
        "mp4",
        109_200_000,
        dynamic_range="HDR10",
    )

    assert codec_family(hdr) == "AV1"
    assert variant_label(hdr) == "AV1 · HDR10 · MP4 · 104.1 MB · Video only"
    assert hdr.is_hdr is True


def test_variant_label_distinguishes_combined_audio_video():
    combined = make_format(
        "22", "1280x720", 30, "avc1", "mp4", 10_000_000, has_audio=True
    )

    assert variant_label(combined).endswith(" · Audio + video")


def test_variant_options_keeps_duplicate_display_labels_selectable():
    formats = [
        make_format("a", "1920x1080", 60, "avc1", "mp4", 10_000_000),
        make_format("b", "1920x1080", 60, "avc1", "mp4", 10_000_000),
    ]

    options = variant_options(formats)

    assert [label for label, _ in options][1].endswith(" · Format 2")
    assert [fmt.format_id for _, fmt in options] == ["a", "b"]


def test_text_track_options_keeps_subtitles_and_transcripts_separate():
    options = text_track_options(
        [TextTrackInfo("en", "English", "vtt")],
        [TextTrackInfo("tr", "Turkish", "srv3", is_auto=True)],
    )

    assert options[0] == ("No subtitles or transcript", None)
    assert options[1][0].startswith("Subtitle: English")
    assert options[2][0].startswith("Transcript: Turkish")


def test_video_only_format_automatically_pairs_best_audio():
    video = make_format("137", "mp4", "1920x1080", 60, "avc1", 10_000_000)
    audio = [make_format("140", "m4a", "", 0, "mp4a", 2_000_000)]

    assert resolve_audio_format_id(video, "auto", None, audio) == "140"


def test_explicit_no_audio_selection_is_respected():
    video = make_format("137", "mp4", "1920x1080", 60, "avc1", 10_000_000)
    audio = [make_format("140", "m4a", "", 0, "mp4a", 2_000_000)]

    assert resolve_audio_format_id(video, "none", None, audio) is None


def test_webm_video_prefers_compatible_opus_audio():
    video = make_format("248", "1920x1080", 60, "vp9", "webm", 10_000_000)
    audio = [
        make_format("140", "", 0, "mp4a", "m4a", 5_000_000),
        make_format("251", "", 0, "opus", "webm", 4_000_000),
    ]

    assert resolve_audio_format_id(video, "auto", None, audio) == "251"


def test_incompatible_video_audio_pair_falls_back_to_mkv_merge():
    video = make_format("248", "1920x1080", 60, "vp9", "webm", 10_000_000)
    audio = make_format("140", "", 0, "mp4a", "m4a", 5_000_000)

    assert resolve_merge_format(video, audio) == "mkv"


def test_video_format_lookup_uses_the_selected_format_id():
    formats = [make_format("137", "mp4", "1920x1080", 60, "avc1", 10_000_000)]

    assert video_format_by_id(formats, "137") is formats[0]
    assert video_format_by_id(formats, "missing") is None


def test_hdr_detection_does_not_treat_regular_dv_codec_text_as_hdr():
    fmt = make_format(
        "c", "1920x1080", 30, "avc1", "mp4", 1_000_000,
        dynamic_range="SDR",
    )
    fmt.format_note = "video"
    assert fmt.is_hdr is False


def test_format_info_keeps_legacy_positional_audio_flags_stable():
    fmt = FormatInfo("x", "mp4", "1920x1080", 30, "avc1", None, None, None, None, "1080p", True, False)
    assert fmt.has_video is True
    assert fmt.has_audio is False
    assert fmt.dynamic_range == ""


class FakeButton:
    def __init__(self):
        self.configured = {}
        self.grid_count = 0
        self.forget_count = 0

    def configure(self, **kwargs):
        self.configured.update(kwargs)

    def grid(self, **kwargs):
        self.grid_count += 1
        self.grid_options = kwargs

    def grid_forget(self):
        self.forget_count += 1


class FakeTabView:
    def __init__(self, selected):
        self.selected = selected

    def get(self):
        return self.selected

    def set(self, value):
        self.selected = value


class FakePanel:
    def __init__(self):
        self.activation_count = 0

    def on_tab_activated(self):
        self.activation_count += 1

    def select_session(self, folder_name):
        self.selected_folder = folder_name


def test_download_success_button_is_replaced_by_red_failure_state():
    from src.gui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    window.go_convert_btn = FakeButton()
    window._download_result_visible = True
    window._download_error = ""
    window._pending_session_folder = ""
    window._go_to_convert_tab = lambda: None
    window._on_download_failure_clicked = lambda: None

    window._show_download_success("clip.mp4")
    assert window.go_convert_btn.configured["fg_color"] == "#2e7d32"
    assert "Download Complete" in window.go_convert_btn.configured["text"]

    window._show_download_failure("network error")
    assert window.go_convert_btn.configured["fg_color"] == "#b71c1c"
    assert window.go_convert_btn.configured["text"] == "❌ DOWNLOAD FAILED!!!"
    assert window._download_error == "network error"


def test_download_result_button_is_hidden_when_leaving_download_tab():
    from src.gui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    window.go_convert_btn = FakeButton()
    window._download_result_visible = True
    window._hide_download_result = MainWindow._hide_download_result.__get__(window)
    window._on_tab_changed = MainWindow._on_tab_changed.__get__(window)
    window.tabview = FakeTabView("Convert")
    window.convert_panel = FakePanel()
    window.audio_panel = FakePanel()
    window._on_tab_changed()

    assert window.go_convert_btn.forget_count == 1
    assert window._download_result_visible is False


def test_download_result_reset_hides_old_state_and_restores_green_defaults():
    from src.gui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    window.go_convert_btn = FakeButton()
    window._download_result_visible = True
    window._download_error = "old failure"
    window._hide_download_result = MainWindow._hide_download_result.__get__(window)
    window._reset_download_result = MainWindow._reset_download_result.__get__(window)
    window._go_to_convert_tab = lambda: None

    window._reset_download_result()

    assert window.go_convert_btn.forget_count == 1
    assert window._download_error == ""
    assert window.go_convert_btn.configured["fg_color"] == "#2e7d32"
    assert window.go_convert_btn.configured["state"] == "normal"


def test_success_shortcut_hides_itself_before_switching_to_convert():
    from src.gui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    window.go_convert_btn = FakeButton()
    window._download_result_visible = True
    window._pending_session_folder = ""
    window._hide_download_result = MainWindow._hide_download_result.__get__(window)
    window._go_to_convert_tab = MainWindow._go_to_convert_tab.__get__(window)
    window.tabview = FakeTabView("Download")
    window.convert_panel = FakePanel()

    window._go_to_convert_tab()

    assert window.go_convert_btn.forget_count == 1
    assert window.tabview.get() == "Convert"
    assert window.convert_panel.activation_count == 1


def test_success_shortcut_remembers_the_downloaded_session_for_convert():
    from src.gui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    window.go_convert_btn = FakeButton()
    window._download_result_visible = False
    window._download_error = ""
    window._pending_session_folder = ""
    MainWindow._show_download_success(window, "clip.mp4", "new-session")

    assert window._pending_session_folder == "new-session"


def test_auto_audio_mode_is_not_overridden_by_clearing_audio_selection():
    from src.gui.format_selector import FormatSelector

    selector = FormatSelector.__new__(FormatSelector)
    selector._audio_mode_var = type("Var", (), {"get": lambda self: "auto", "set": lambda self, value: None})()
    selector._audio_var = type("Var", (), {"get": lambda self: "", "set": lambda self, value: None})()
    selector._syncing_audio = False

    selector._sync_audio_mode()
    assert selector._audio_mode_var.get() == "auto"


def test_failure_button_keeps_exact_detail_for_click_handler():
    from src.gui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    window.go_convert_btn = FakeButton()
    window._download_result_visible = False
    window._download_error = ""
    MainWindow._show_download_failure(window, "HTTP 503 from media endpoint")

    assert window._download_error == "HTTP 503 from media endpoint"
    assert window.go_convert_btn.configured["text"] == "❌ DOWNLOAD FAILED!!!"


def test_download_file_discovery_ignores_caption_sidecars():
    from src.gui.main_window import MainWindow

    with __import__("tempfile").TemporaryDirectory() as directory:
        from pathlib import Path
        video = Path(directory) / "clip.mp4"
        subtitle = Path(directory) / "clip.tr.vtt"
        video.write_bytes(b"video")
        subtitle.write_bytes(b"subtitle")
        window = MainWindow.__new__(MainWindow)

        assert window._find_downloaded(directory) == str(video)
        assert window._find_subtitle_file(directory) == str(subtitle)


def test_format_selector_repopulation_replaces_audio_variable_traces():
    import customtkinter as ctk
    from src.gui.format_selector import FormatSelector

    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.withdraw()
    try:
        selector = FormatSelector(root)
        video = make_format("137", "1920x1080", 60, "avc1", "mp4", 10_000_000)
        audio = make_format("140", "", 0, "mp4a", "m4a", 1_000_000)
        selector.populate([video], [audio], [], [])
        first_trace = selector._audio_mode_trace
        selector.populate([video], [audio], [], [])
        assert selector._audio_mode_trace != first_trace
    finally:
        root.destroy()

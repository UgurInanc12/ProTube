"""Compact format selection panel with resolution, codec, and HDR controls."""
import customtkinter as ctk

from src.core.download_options import (
    DOWNLOAD_MODE_AUDIO,
    DOWNLOAD_MODE_LABELS,
    DOWNLOAD_MODE_TEXT,
    DOWNLOAD_MODE_VIDEO,
)
from src.core.format_options import (
    VideoFormatGroup,
    group_video_formats,
    text_track_options,
    variant_options,
)
from src.core.models import FormatInfo, SubtitleInfo, TextTrackInfo


class FormatSelector(ctk.CTkFrame):
    """Select a quality group first, then a codec/HDR variant."""

    MODE_ORDER = (DOWNLOAD_MODE_VIDEO, DOWNLOAD_MODE_AUDIO, DOWNLOAD_MODE_TEXT)

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._video_var = ctk.StringVar()
        self._audio_var = ctk.StringVar(value="")
        self._audio_mode_var = ctk.StringVar(value="auto")
        self._download_mode_var = ctk.StringVar(value=DOWNLOAD_MODE_VIDEO)
        self._syncing_audio = False
        self._audio_mode_trace = None
        self._audio_selection_trace = None
        self._subtitle_var = ctk.StringVar(value="none")
        self._text_track_var = ctk.StringVar(value="No subtitles or transcript")
        self._text_tracks: dict[str, TextTrackInfo | None] = {}
        self._quality_var = ctk.StringVar()
        self._variant_var = ctk.StringVar()
        self._video_groups: list[VideoFormatGroup] = []
        self._video_variants: dict[str, FormatInfo] = {}
        self._format_widgets = []
        self._subtitle_widgets = []
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        mode_frame = ctk.CTkFrame(self)
        mode_frame.grid(row=0, column=0, padx=10, pady=(5, 0), sticky="ew")
        ctk.CTkLabel(
            mode_frame, text="Download type:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=(10, 12), pady=8)
        for mode in self.MODE_ORDER:
            ctk.CTkRadioButton(
                mode_frame,
                text=DOWNLOAD_MODE_LABELS[mode],
                variable=self._download_mode_var,
                value=mode,
                command=self._on_download_mode_changed,
                font=ctk.CTkFont(size=12),
            ).pack(side="left", padx=(0, 14), pady=8)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, padx=10, pady=(5, 0), sticky="nsew")
        self.tab_video = self.tabview.add("Video Formats")
        self.tab_audio = self.tabview.add("Audio Tracks")
        self.tab_subs = self.tabview.add("Subtitles")
        self.tabview.set("Video Formats")

        self.video_scroll = ctk.CTkScrollableFrame(self.tab_video, height=280)
        self.video_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        self.audio_scroll = ctk.CTkScrollableFrame(self.tab_audio, height=280)
        self.audio_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        self.sub_scroll = ctk.CTkScrollableFrame(self.tab_subs, height=280)
        self.sub_scroll.pack(fill="both", expand=True, padx=5, pady=5)

    def _on_download_mode_changed(self):
        """Open the tab that matters for the chosen download type."""
        mode = self._download_mode_var.get()
        if mode == DOWNLOAD_MODE_AUDIO:
            self.tabview.set("Audio Tracks")
        elif mode == DOWNLOAD_MODE_TEXT:
            self.tabview.set("Subtitles")
        else:
            self.tabview.set("Video Formats")

    def set_download_mode(self, mode: str):
        """Select a download type programmatically."""
        if mode in self.MODE_ORDER:
            self._download_mode_var.set(mode)
            self._on_download_mode_changed()

    def populate(
        self,
        video_formats: list[FormatInfo],
        audio_formats: list[FormatInfo],
        combined_formats: list[FormatInfo],
        subtitles: list[SubtitleInfo],
        automatic_captions: list[TextTrackInfo] | None = None,
    ):
        """Populate all tabs and reset selections for a new video."""
        self._clear_all()
        self._build_video_tab(combined_formats + video_formats)
        self._build_audio_tab(audio_formats)
        self._build_subtitle_tab(subtitles, automatic_captions or [])

    def _build_video_tab(self, formats: list[FormatInfo]):
        self._video_groups = group_video_formats(formats)
        if not self._video_groups:
            ctk.CTkLabel(
                self.video_scroll, text="No video formats available",
                font=ctk.CTkFont(size=13),
            ).pack(pady=20)
            return

        ctk.CTkLabel(
            self.video_scroll, text="Choose quality, then codec and HDR variant:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(5, 8))

        selector_frame = ctk.CTkFrame(self.video_scroll, fg_color="transparent")
        selector_frame.pack(fill="x", pady=(0, 5))
        selector_frame.grid_columnconfigure(0, weight=1)
        selector_frame.grid_columnconfigure(1, weight=1)

        quality_frame = ctk.CTkFrame(selector_frame, fg_color="transparent")
        quality_frame.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkLabel(
            quality_frame, text="Video quality", anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.quality_menu = ctk.CTkOptionMenu(
            quality_frame,
            variable=self._quality_var,
            values=[group.label for group in self._video_groups],
            command=self._on_quality_changed,
        )
        self.quality_menu.pack(fill="x", expand=True)

        variant_frame = ctk.CTkFrame(selector_frame, fg_color="transparent")
        variant_frame.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ctk.CTkLabel(
            variant_frame, text="Codec / HDR variant", anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.variant_menu = ctk.CTkOptionMenu(
            variant_frame,
            variable=self._variant_var,
            values=[],
            command=self._on_variant_changed,
        )
        self.variant_menu.pack(fill="x", expand=True)

        self.video_detail = ctk.CTkLabel(
            self.video_scroll, text="", anchor="w",
            font=ctk.CTkFont(size=11), text_color="#8aa4c8",
        )
        self.video_detail.pack(anchor="w", pady=(0, 10))

        self._quality_var.set(self._video_groups[0].label)
        self._on_quality_changed(self._video_groups[0].label)

    def _on_quality_changed(self, label: str):
        group = next((item for item in self._video_groups if item.label == label), None)
        if group is None:
            self._variant_menu_values([])
            return
        options = variant_options(group.formats)
        self._video_variants = dict(options)
        values = list(self._video_variants)
        self.variant_menu.configure(values=values)
        if values:
            self._variant_var.set(values[0])
            self._on_variant_changed(values[0])

    def _variant_menu_values(self, values: list[str]):
        if hasattr(self, "variant_menu"):
            self.variant_menu.configure(values=values)
        self._variant_var.set(values[0] if values else "")

    def _on_variant_changed(self, label: str):
        fmt = self._video_variants.get(label)
        self._video_var.set(fmt.format_id if fmt else "")
        if hasattr(self, "video_detail"):
            self.video_detail.configure(
                text=(f"Selected: {label}" if label else "Select a video variant")
            )

    def _build_audio_tab(self, audio_formats: list[FormatInfo]):
        self._remove_audio_traces()
        ctk.CTkLabel(
            self.audio_scroll, text="Select audio track:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(5, 5))
        self._add_radio_row(
            self.audio_scroll,
            "Auto-select best audio (highest quality)",
            self._audio_mode_var, "auto",
        )
        self._add_radio_row(
            self.audio_scroll,
            "No audio (video only)",
            self._audio_mode_var, "none",
        )
        for fmt in audio_formats:
            lang_note = f" ({fmt.format_note})" if fmt.format_note else ""
            label = f"{fmt.codec.upper()}{lang_note}  {fmt.abr or '?'}kbps  .{fmt.ext}"
            self._add_radio_row(self.audio_scroll, label, self._audio_var, fmt.format_id)

        self._audio_mode_trace = self._audio_mode_var.trace_add("write", self._sync_audio_mode)
        self._audio_selection_trace = self._audio_var.trace_add("write", self._sync_audio_selection)

    def _remove_audio_traces(self):
        """Remove old variable observers before repopulating the audio tab."""
        if self._audio_mode_trace:
            self._audio_mode_var.trace_remove("write", self._audio_mode_trace)
            self._audio_mode_trace = None
        if self._audio_selection_trace:
            self._audio_var.trace_remove("write", self._audio_selection_trace)
            self._audio_selection_trace = None

    def _sync_audio_mode(self, *_):
        """Clear a specific track when the user switches back to auto or no audio."""
        if self._audio_mode_var.get() != "format" and not self._syncing_audio:
            self._syncing_audio = True
            self._audio_var.set("")
            self._syncing_audio = False

    def _sync_audio_selection(self, *_):
        """Make selecting a concrete audio track opt into that track."""
        if self._audio_var.get() and not self._syncing_audio:
            self._syncing_audio = True
            self._audio_mode_var.set("format")
            self._syncing_audio = False

    def _build_subtitle_tab(
        self,
        subtitles: list[SubtitleInfo],
        automatic_captions: list[TextTrackInfo],
    ):
        ctk.CTkLabel(
            self.sub_scroll, text="Select subtitles to download:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(5, 5))
        self._add_radio_row(self.sub_scroll, "No subtitles", self._subtitle_var, "none")
        for sub in subtitles:
            self._add_radio_row(self.sub_scroll, sub.label, self._subtitle_var, sub.language)
        if not subtitles:
            ctk.CTkLabel(
                self.sub_scroll, text="No subtitles available for this video",
                font=ctk.CTkFont(size=12), text_color="gray",
            ).pack(anchor="w", padx=25, pady=5)

        options = text_track_options(subtitles, automatic_captions)
        self._text_tracks = dict(options)
        ctk.CTkLabel(
            self.sub_scroll, text="Additional text file:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(18, 5))
        self.text_track_menu = ctk.CTkOptionMenu(
            self.sub_scroll,
            variable=self._text_track_var,
            values=list(self._text_tracks),
        )
        self.text_track_menu.pack(fill="x", padx=10, pady=(0, 5))

    def _add_radio_row(self, parent, label: str, var: ctk.StringVar, value: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        if var is self._subtitle_var:
            self._subtitle_widgets.append(row)
        self._format_widgets.append(row)
        ctk.CTkRadioButton(
            row, text=label, variable=var, value=value,
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

    def _clear_all(self):
        self._remove_audio_traces()
        for frame in [self.video_scroll, self.audio_scroll, self.sub_scroll]:
            for widget in frame.winfo_children():
                widget.destroy()
        self._format_widgets.clear()
        self._subtitle_widgets.clear()
        self._video_groups = []
        self._video_variants.clear()
        self._video_var.set("")
        self._quality_var.set("")
        self._variant_var.set("")
        self._audio_var.set("")
        self._audio_mode_var.set("auto")
        self._subtitle_var.set("none")
        self._text_track_var.set("No subtitles or transcript")
        self._text_tracks.clear()

    def get_selections(self) -> dict:
        """Return the download type, video variant, audio track, and subtitles."""
        sub = self._subtitle_var.get()
        return {
            "download_mode": self._download_mode_var.get(),
            "video_format": self._video_var.get(),
            "audio_format": self._audio_var.get() or None,
            "audio_mode": self._audio_mode_var.get(),
            "subtitle_lang": None if sub == "none" else sub,
            "text_track": self._text_tracks.get(self._text_track_var.get()),
        }

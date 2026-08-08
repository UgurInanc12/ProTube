"""Format selection panel with tabs for video, audio, and subtitles."""
import customtkinter as ctk
from src.core.models import FormatInfo, SubtitleInfo


class FormatSelector(ctk.CTkFrame):
    """Panel for selecting video format, audio track, and subtitle language."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._video_var = ctk.StringVar()
        self._audio_var = ctk.StringVar(value="")
        self._subtitle_var = ctk.StringVar(value="none")
        self._format_widgets = []
        self._subtitle_widgets = []
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Tab view for format categories
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=10, pady=(5, 0), sticky="nsew")

        self.tab_video = self.tabview.add("Video Formats")
        self.tab_audio = self.tabview.add("Audio Tracks")
        self.tab_subs = self.tabview.add("Subtitles")

        self.tabview.set("Video Formats")

        # Scrollable frames for each tab
        self.video_scroll = ctk.CTkScrollableFrame(self.tab_video, height=280)
        self.video_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self.audio_scroll = ctk.CTkScrollableFrame(self.tab_audio, height=280)
        self.audio_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self.sub_scroll = ctk.CTkScrollableFrame(self.tab_subs, height=280)
        self.sub_scroll.pack(fill="both", expand=True, padx=5, pady=5)

    def populate(
        self,
        video_formats: list[FormatInfo],
        audio_formats: list[FormatInfo],
        combined_formats: list[FormatInfo],
        subtitles: list[SubtitleInfo],
    ):
        """Populate format lists with available options."""
        self._clear_all()

        # Video tab: combined formats + video-only, sorted by resolution descending
        all_video = combined_formats + video_formats
        # Sort by resolution height descending, then by filesize descending
        def _res_key(fmt):
            try:
                h = int(fmt.resolution.split("x")[1]) if fmt.resolution else 0
                return (h, fmt.filesize or 0)
            except (IndexError, ValueError):
                return (0, 0)
        all_video.sort(key=_res_key, reverse=True)
        if not all_video:
            ctk.CTkLabel(
                self.video_scroll, text="No video formats available",
                font=ctk.CTkFont(size=13),
            ).pack(pady=20)
        else:
            ctk.CTkLabel(
                self.video_scroll,
                text="Select video quality:",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(anchor="w", pady=(5, 5))

            first = True
            for fmt in all_video:
                self._add_format_row(
                    self.video_scroll, fmt, self._video_var, first
                )
                first = False

        # Audio tab
        ctk.CTkLabel(
            self.audio_scroll,
            text="Select audio track:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(5, 5))

        # "Use combined" option
        self._add_radio_row(
            self.audio_scroll,
            "Use combined format audio (no separate track)",
            self._audio_var,
            "",
        )

        if audio_formats:
            for fmt in audio_formats:
                lang_note = f" ({fmt.format_note})" if fmt.format_note else ""
                label = (
                    f"{fmt.codec.upper()}{lang_note}  "
                    f"{fmt.abr or '?'}kbps  .{fmt.ext}"
                )
                self._add_radio_row(
                    self.audio_scroll, label, self._audio_var, fmt.format_id,
                )

        # Subtitle tab
        ctk.CTkLabel(
            self.sub_scroll,
            text="Select subtitles to download:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(5, 5))

        self._add_radio_row(
            self.sub_scroll, "No subtitles", self._subtitle_var, "none",
        )

        if subtitles:
            for sub in subtitles:
                self._add_radio_row(
                    self.sub_scroll, sub.label, self._subtitle_var, sub.language,
                )
        else:
            ctk.CTkLabel(
                self.sub_scroll,
                text="No subtitles available for this video",
                font=ctk.CTkFont(size=12), text_color="gray",
            ).pack(anchor="w", padx=25, pady=5)

    def _add_format_row(
        self, parent, fmt: FormatInfo, var: ctk.StringVar, select_first: bool
    ):
        """Add a radio button row for a format."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=3)
        self._format_widgets.append(row)

        # Build label with metadata
        parts = []
        if fmt.resolution_short:
            parts.append(fmt.resolution_short)
        if fmt.fps and fmt.fps > 30:
            parts.append(f"{int(fmt.fps)}fps")
        if fmt.codec:
            parts.append(fmt.codec.upper())
        if fmt.filesize_mb:
            parts.append(f"{fmt.filesize_mb:.1f} MB")
        parts.append(f".{fmt.ext}")
        if fmt.format_note:
            parts.append(f"({fmt.format_note})")

        label = "  ".join(parts)
        rb = ctk.CTkRadioButton(
            row, text=label, variable=var, value=fmt.format_id,
            font=ctk.CTkFont(size=12),
        )
        rb.pack(side="left")

        if select_first:
            var.set(fmt.format_id)

    def _add_radio_row(
        self, parent, label: str, var: ctk.StringVar, value: str,
    ):
        """Add a simple radio button row."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        if var is self._subtitle_var:
            self._subtitle_widgets.append(row)
        self._format_widgets.append(row)

        rb = ctk.CTkRadioButton(
            row, text=label, variable=var, value=value,
            font=ctk.CTkFont(size=12),
        )
        rb.pack(side="left")

    def _clear_all(self):
        """Remove all widgets from the scrollable frames."""
        # Destroy all children of each scroll frame
        for frame in [self.video_scroll, self.audio_scroll, self.sub_scroll]:
            for w in frame.winfo_children():
                w.destroy()
        self._format_widgets.clear()
        self._subtitle_widgets.clear()

        # Reset selections
        self._video_var.set("")
        self._audio_var.set("")
        self._subtitle_var.set("none")

    def get_selections(self) -> dict:
        """Return the user's format selections."""
        sub = self._subtitle_var.get()
        return {
            "video_format": self._video_var.get(),
            "audio_format": self._audio_var.get() or None,
            "subtitle_lang": None if sub == "none" else sub,
        }

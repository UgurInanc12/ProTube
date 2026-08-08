"""Session view panel: download progress and post-processing controls."""
import os
import customtkinter as ctk
from threading import Thread
from src.core.models import DownloadProgress, DownloadStatus


class SessionPanel(ctk.CTkFrame):
    """Panel for a single video session: download progress and post-processing."""

    def __init__(self, master, video_title: str, ffmpeg_manager, **kwargs):
        super().__init__(master, **kwargs)
        self.video_title = video_title
        self.ffmpeg = ffmpeg_manager
        self.output_path = ""
        self.downloaded_file = ""
        self._on_process_callback = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # Header bar with title and close
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=10, pady=(8, 2), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_short = self.video_title[:60] + "..." if len(self.video_title) > 60 else self.video_title
        ctk.CTkLabel(
            header,
            text=f"📥 {title_short}",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self, height=14)
        self.progress_bar.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.progress_bar.set(0)

        # Progress info text
        self.progress_info = ctk.CTkLabel(
            self, text="Waiting to start...",
            font=ctk.CTkFont(size=11),
        )
        self.progress_info.grid(row=2, column=0, padx=10, pady=2, sticky="w")

        # Post-processing section (hidden until download complete)
        self.post_frame = ctk.CTkFrame(self)
        self.post_frame.grid_columnconfigure(1, weight=1)

        # Section title
        ctk.CTkLabel(
            self.post_frame,
            text="Post-Processing",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 8), sticky="w")

        # Convert format dropdown
        ctk.CTkLabel(
            self.post_frame, text="Convert to:", font=ctk.CTkFont(size=12),
        ).grid(row=1, column=0, padx=10, pady=4, sticky="w")
        self.format_var = ctk.StringVar(value="mp4")
        self.format_menu = ctk.CTkOptionMenu(
            self.post_frame,
            values=["mp4", "mkv", "avi", "webm", "mov"],
            variable=self.format_var,
            width=120,
        )
        self.format_menu.grid(row=1, column=1, padx=5, pady=4, sticky="w")

        # Bitrate dropdown
        ctk.CTkLabel(
            self.post_frame, text="Video bitrate:", font=ctk.CTkFont(size=12),
        ).grid(row=2, column=0, padx=10, pady=4, sticky="w")
        self.bitrate_var = ctk.StringVar(value="")
        self.bitrate_menu = ctk.CTkOptionMenu(
            self.post_frame,
            values=["Original", "1M", "2M", "5M", "10M", "20M"],
            variable=self.bitrate_var,
            width=120,
        )
        self.bitrate_menu.grid(row=2, column=1, padx=5, pady=4, sticky="w")

        # Embed subtitles checkbox
        self.embed_var = ctk.BooleanVar(value=False)
        self.embed_check = ctk.CTkCheckBox(
            self.post_frame,
            text="Embed subtitles (if downloaded)",
            variable=self.embed_var,
        )
        self.embed_check.grid(
            row=3, column=0, columnspan=2, padx=10, pady=4, sticky="w"
        )

        # Audio extract section
        ctk.CTkLabel(
            self.post_frame,
            text="Extract Audio:",
            font=ctk.CTkFont(size=12),
        ).grid(row=4, column=0, padx=10, pady=(8, 4), sticky="w")
        self.audio_format_var = ctk.StringVar(value="mp3")
        audio_frame = ctk.CTkFrame(self.post_frame, fg_color="transparent")
        audio_frame.grid(row=4, column=1, padx=5, pady=(8, 4), sticky="w")
        self.audio_menu = ctk.CTkOptionMenu(
            audio_frame,
            values=["mp3", "aac", "wav", "ogg", "m4a"],
            variable=self.audio_format_var,
            width=100,
        )
        self.audio_menu.pack(side="left", padx=(0, 5))
        self.audio_extract_btn = ctk.CTkButton(
            audio_frame,
            text="Extract",
            width=70,
            height=30,
            command=self._on_extract_audio,
        )
        self.audio_extract_btn.pack(side="left")

        # Process button
        self.process_btn = ctk.CTkButton(
            self.post_frame,
            text="▶ Process",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_process,
            height=36,
        )
        self.process_btn.grid(
            row=5, column=0, columnspan=2, padx=10, pady=(10, 10), sticky="ew"
        )

    def set_process_callback(self, callback):
        """Set callback for process requests: callback(action, params)."""
        self._on_process_callback = callback

    def update_progress(self, progress: DownloadProgress):
        """Update progress bar and info from download hook."""
        self.progress_bar.set(progress.percent / 100)
        parts = [f"{progress.percent:.1f}%"]
        if progress.speed:
            parts.append(progress.speed)
        if progress.eta:
            parts.append(f"ETA: {progress.eta}")
        self.progress_info.configure(text=" | ".join(parts))

    def on_download_complete(self, output_path: str):
        """Called when download finishes successfully."""
        self.output_path = output_path
        self.downloaded_file = output_path
        self.progress_bar.set(1.0)
        self.progress_info.configure(
            text=f"✅ Download complete: {os.path.basename(output_path)}"
        )
        self.post_frame.grid(
            row=3, column=0, padx=10, pady=(10, 10), sticky="ew"
        )

    def on_download_failed(self, error: str = ""):
        """Called when download fails."""
        self.progress_info.configure(text=f"❌ Download failed: {error}")

    def _on_process(self):
        """Handle transcode processing."""
        if self._on_process_callback:
            fmt = self.format_var.get()
            bitrate = self.bitrate_var.get()
            if bitrate == "Original":
                bitrate = ""
            embed = self.embed_var.get()
            self._on_process_callback("transcode", {
                "input_path": self.downloaded_file,
                "output_format": fmt,
                "video_bitrate": bitrate,
                "embed_subs": embed,
            })

    def _on_extract_audio(self):
        """Handle audio extraction."""
        if self._on_process_callback:
            fmt = self.audio_format_var.get()
            self._on_process_callback("extract_audio", {
                "input_path": self.downloaded_file,
                "audio_format": fmt,
            })

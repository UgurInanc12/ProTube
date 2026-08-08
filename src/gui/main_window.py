"""Main window with tabbed interface: Download | Convert | Extract Audio."""
import os
import glob
import logging
import threading
import customtkinter as ctk
from threading import Thread
from src.core.engine import VideoEngine
from src.core.models import DownloadProgress, DownloadStatus, SessionState
from src.core.session_manager import SessionManager, SessionRecord
from src.gui.url_bar import URLBar
from src.gui.video_info import VideoInfoPanel
from src.gui.format_selector import FormatSelector
from src.gui.convert_panel import ConvertPanel
from src.gui.audio_panel import AudioPanel

log = logging.getLogger("protube")


class MainWindow(ctk.CTkFrame):
    """Tabbed main window: Download, Convert, Extract Audio."""

    def __init__(self, master, ffmpeg_manager, **kwargs):
        super().__init__(master, **kwargs)
        self.ffmpeg = ffmpeg_manager
        self.sm = SessionManager()
        log.info(f"Sessions directory: {self.sm.base_dir}")
        log.info(f"Loaded {len(self.sm._records)} existing sessions")
        self._current_metadata = None
        self._status_label = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Tab view ──────────────────────────────────────────────
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=5, pady=(5, 0))

        self.tab_download = self.tabview.add("Download")
        self.tab_convert = self.tabview.add("Convert")
        self.tab_audio = self.tabview.add("Extract Audio")

        self.tabview.set("Download")

        # Build each tab
        self._build_download_tab()
        self._build_convert_tab()
        self._build_audio_tab()

        # Tab switch callback to refresh session lists
        self.tabview.configure(command=self._on_tab_changed)

        # ── Status bar ────────────────────────────────────────────
        self.status_frame = ctk.CTkFrame(self, height=28)
        self.status_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(2, 5))
        self._status_label = ctk.CTkLabel(
            self.status_frame, text="Ready", font=ctk.CTkFont(size=11),
        )
        self._status_label.pack(side="left", padx=10, pady=2)

    # ═══════════════════════════════════════════════════════════════
    # DOWNLOAD TAB
    # ═══════════════════════════════════════════════════════════════

    def _build_download_tab(self):
        tab = self.tab_download
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=0)
        tab.grid_rowconfigure(2, weight=1)
        tab.grid_rowconfigure(3, weight=0)

        self.url_bar = URLBar(tab, on_fetch=self._on_fetch)
        self.url_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        self.video_info = VideoInfoPanel(tab)
        self.format_selector = FormatSelector(tab)

        # Download + Cancel button row
        dl_btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        dl_btn_row.grid_columnconfigure(0, weight=1)

        self.download_btn = ctk.CTkButton(
            dl_btn_row, text="⬇ Download",
            height=46, font=ctk.CTkFont(size=15, weight="bold"),
            command=self._on_download,
            fg_color="#1a73e8", hover_color="#1557b0",
        )
        self.download_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        self.dl_cancel_btn = ctk.CTkButton(
            dl_btn_row, text="Cancel", font=ctk.CTkFont(size=12),
            height=46, width=80, fg_color="#c62828", hover_color="#b71c1c",
            command=self._on_dl_cancel, state="disabled",
        )
        self.dl_cancel_btn.grid(row=0, column=1)

        # Download + Cancel button row (initially hidden)
        self.dl_btn_row = dl_btn_row
        self._dl_cancel_event = threading.Event()

        # "Go to Convert" button
        self.go_convert_btn = ctk.CTkButton(
            tab,
            text="✅ Download Complete. Open in Convert Tab →",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            command=self._go_to_convert_tab,
            fg_color="#2e7d32", hover_color="#1b5e20",
        )

    def _on_fetch(self, url: str):
        """Fetch video metadata in background."""
        self._status("Fetching video metadata...")

        def fetch():
            engine = VideoEngine()
            try:
                data = engine.fetch_metadata(url)
                self.after(0, lambda: self._display_metadata(data))
            except Exception as e:
                msg = str(e)
                log.error(f"Fetch failed: {msg[:300]}")
                if "HTTP Error" in msg:
                    msg = "Video unavailable or network error"
                elif "Unsupported URL" in msg:
                    msg = "Unsupported URL. Make sure it's a valid YouTube link."
                self.after(0, lambda: self._show_error(msg))
            finally:
                self.after(0, self.url_bar.set_ready)

        Thread(target=fetch, daemon=True).start()

    def _display_metadata(self, data: dict):
        """Show fetched metadata and format selector."""
        self._current_metadata = data
        video = data["video"]

        # Video info
        self.video_info.update_info(video)
        self.video_info.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        # Format selector
        self.format_selector.populate(
            video_formats=data["video_formats"],
            audio_formats=data["audio_formats"],
            combined_formats=data["combined_formats"],
            subtitles=data["subtitles"],
        )
        self.format_selector.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        # Download button row
        self.dl_btn_row.grid(row=3, column=0, padx=10, pady=(5, 15), sticky="ew")

        total_fmts = len(data["video_formats"]) + len(data["combined_formats"])
        self._status(
            f"✅ {video.title[:70]} | "
            f"{total_fmts} video, {len(data['audio_formats'])} audio, "
            f"{len(data['subtitles'])} subtitles"
        )

    def _on_download(self):
        """Start download with selected options."""
        if not self._current_metadata:
            return

        selections = self.format_selector.get_selections()
        video_fmt_id = selections["video_format"]
        if not video_fmt_id:
            self._show_error("Please select a video format.")
            return

        video = self._current_metadata["video"]
        folder_name = self.sm.create_session(video.id, video.title, video.url)
        output_dir = str(self.sm.session_dir(folder_name))
        log.info(f"Download session: '{folder_name}' -> {output_dir}")

        self._status(f"Downloading: {video.title[:80]}")
        self.download_btn.configure(state="disabled", text="Downloading...")
        self.dl_cancel_btn.configure(state="normal")
        self._dl_cancel_event.clear()

        def download():
            progress = {"last_pct": 0}

            def progress_callback(p: DownloadProgress):
                if self._dl_cancel_event.is_set():
                    return
                if p.percent > progress["last_pct"]:
                    progress["last_pct"] = p.percent
                    self.after(0, lambda pct=p.percent, spd=p.speed: self._status(
                        f"⬇ {pct:.0f}% {spd} | {video.title[:60]}"
                    ))

            engine = VideoEngine(progress_callback=progress_callback)
            result = engine.download(
                url=video.url, output_dir=output_dir,
                format_id=video_fmt_id,
                audio_format_id=selections["audio_format"],
                subtitle_lang=selections["subtitle_lang"],
                embed_subs=False,
            )

            if self._dl_cancel_event.is_set():
                self.after(0, lambda: self._status("🚫 Download cancelled"))
                self.after(0, lambda: self.dl_cancel_btn.configure(state="disabled"))
                self.after(0, lambda: self.download_btn.configure(state="normal", text="⬇ Download"))
                return

            if result == 0:
                downloaded = self._find_downloaded(output_dir)
                if downloaded:
                    rec = SessionRecord(
                        video_id=video.id, title=video.title, url=video.url,
                        downloaded_file=downloaded, video_format=video_fmt_id,
                        audio_format=selections["audio_format"] or "",
                    )
                    self.sm.record_download(folder_name, rec)
                    self.after(0, lambda: self._status(
                        f"✅ Downloaded: {os.path.basename(downloaded)}"
                    ))
                    self.after(0, lambda: self.go_convert_btn.grid(
                        row=4, column=0, padx=10, pady=(0, 15)
                    ))
                else:
                    self.after(0, lambda: self._status("✅ Download complete"))
            else:
                self.after(0, lambda: self._status("❌ Download failed"))

            self.after(0, lambda: self.dl_cancel_btn.configure(state="disabled"))
            self.after(0, lambda: self.download_btn.configure(state="normal", text="⬇ Download"))

        Thread(target=download, daemon=True).start()

    def _on_dl_cancel(self):
        """Cancel the current download."""
        self._dl_cancel_event.set()
        self.dl_cancel_btn.configure(state="disabled")
        self._status("Cancelling download...")

    def _find_downloaded(self, directory: str) -> str:
        files = glob.glob(os.path.join(directory, "*"))
        files = [f for f in files if os.path.isfile(f)]
        if not files:
            return ""
        return max(files, key=os.path.getctime)

    # ═══════════════════════════════════════════════════════════════
    # CONVERT TAB
    # ═══════════════════════════════════════════════════════════════

    def _build_convert_tab(self):
        self.convert_panel = ConvertPanel(
            self.tab_convert, self.sm, self.ffmpeg,
        )
        self.convert_panel.pack(fill="both", expand=True)

    # ═══════════════════════════════════════════════════════════════
    # EXTRACT AUDIO TAB
    # ═══════════════════════════════════════════════════════════════

    def _build_audio_tab(self):
        self.audio_panel = AudioPanel(
            self.tab_audio, self.sm, self.ffmpeg,
        )
        self.audio_panel.pack(fill="both", expand=True)

    # ═══════════════════════════════════════════════════════════════
    # TAB SWITCHING
    # ═══════════════════════════════════════════════════════════════

    def _on_tab_changed(self):
        """Refresh session lists when switching tabs."""
        current = self.tabview.get()
        log.debug(f"Tab switched to: {current}")
        if current == "Convert":
            self.convert_panel.on_tab_activated()
        elif current == "Extract Audio":
            self.audio_panel.on_tab_activated()

    def _go_to_convert_tab(self):
        """Switch to Convert tab (called from download complete button)."""
        self.tabview.set("Convert")
        self.convert_panel.on_tab_activated()

    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════

    def _status(self, text: str):
        if self._status_label:
            self._status_label.configure(text=text[:150])

    def _show_error(self, message: str):
        self._status(f"❌ {message}")
        dialog = ctk.CTkToplevel(self)
        dialog.title("Error")
        dialog.geometry("420x160")
        dialog.transient(self)
        dialog.grab_set()
        dialog.update_idletasks()
        px = self.winfo_toplevel().winfo_x() + 200
        py = self.winfo_toplevel().winfo_y() + 250
        dialog.geometry(f"+{px}+{py}")
        ctk.CTkLabel(
            dialog, text="Error",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="#ff4d4d",
        ).pack(pady=(15, 5))
        ctk.CTkLabel(
            dialog, text=message, wraplength=380, font=ctk.CTkFont(size=13),
        ).pack(pady=5)
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy, width=100).pack(pady=10)

"""Main window with tabbed interface: Download | Convert | Extract Audio."""
import os
import glob
import logging
import threading
import customtkinter as ctk
from threading import Thread
from src.core.engine import VideoEngine
from src.core.download_options import (
    DOWNLOAD_MODE_AUDIO,
    DOWNLOAD_MODE_TEXT,
    DOWNLOAD_MODE_VIDEO,
    audio_format_by_id,
    resolve_audio_format_id,
    resolve_best_audio_format_id,
    resolve_merge_format,
    video_format_by_id,
)
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
        self._download_result_visible = False
        self._download_error = ""
        self._pending_session_folder = ""
        self._fetch_gen = 0
        self._fetch_active = False
        self._fetch_watchdog_id = None
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

    def _show_download_success(self, filename: str, folder_name: str = ""):
        """Show the green post-download shortcut."""
        self._download_error = ""
        self._pending_session_folder = folder_name or getattr(self, "_pending_session_folder", "")
        self._download_result_visible = True
        self.go_convert_btn.configure(
            text="✅ Download Complete. Open in Convert Tab →",
            fg_color="#2e7d32", hover_color="#1b5e20", state="normal",
            command=self._go_to_convert_tab,
        )
        self.go_convert_btn.grid(row=4, column=0, padx=10, pady=(0, 15))

    def _show_download_failure(self, error: str = ""):
        """Replace the shortcut with a clear, disabled failure indicator."""
        self._download_error = error
        self._download_result_visible = True
        self.go_convert_btn.configure(
            text="❌ DOWNLOAD FAILED!!!",
            fg_color="#b71c1c", hover_color="#8e0000", state="normal",
            command=self._on_download_failure_clicked,
        )
        self.go_convert_btn.grid(row=4, column=0, padx=10, pady=(0, 15))

    def _on_download_failure_clicked(self):
        """Show the preserved failure detail when the red status button is clicked."""
        self._show_error(self._download_error or "The download did not complete.")

    def _hide_download_result(self):
        """Hide the result shortcut when Download is no longer active."""
        if self._download_result_visible:
            self.go_convert_btn.grid_forget()
            self._download_result_visible = False

    def _reset_download_result(self):
        """Clear a previous success or failure state before a new fetch/download."""
        self._download_error = ""
        self._hide_download_result()
        self.go_convert_btn.configure(
            text="✅ Download Complete. Open in Convert Tab →",
            fg_color="#2e7d32", hover_color="#1b5e20", state="normal",
            command=self._go_to_convert_tab,
        )

    FETCH_TIMEOUT_MS = 90_000  # watchdog for a stuck background fetch

    def _on_fetch(self, url: str):
        """Fetch video metadata in the background.

        A watchdog recovers the UI if the request ever gets stuck, so a
        failed fetch can never leave the button disabled forever.
        """
        self._reset_download_result()
        self._status("Fetching video metadata...")
        self._fetch_gen += 1
        gen = self._fetch_gen

        def finish():
            """Run on the UI thread when the fetch thread is done."""
            self._fetch_active = False
            if self._fetch_watchdog_id is not None:
                self.after_cancel(self._fetch_watchdog_id)
                self._fetch_watchdog_id = None
            self.url_bar.set_ready()

        def fetch():
            engine = VideoEngine()
            try:
                data = engine.fetch_metadata(url)
                if gen == self._fetch_gen:
                    self.after(0, lambda: self._display_metadata(data))
            except Exception as e:
                msg = str(e)
                log.error(f"Fetch failed: {msg[:300]}")
                if "HTTP Error" in msg:
                    msg = "Video unavailable or network error"
                elif "Unsupported URL" in msg:
                    msg = "Unsupported URL. Make sure it's a valid YouTube link."
                if gen == self._fetch_gen:
                    self.after(0, lambda: self._show_error(msg))
            finally:
                if gen == self._fetch_gen:
                    self.after(0, finish)

        self._fetch_active = True
        Thread(target=fetch, daemon=True).start()
        self._fetch_watchdog_id = self.after(
            self.FETCH_TIMEOUT_MS, self._fetch_watchdog
        )

    def _fetch_watchdog(self):
        """Recover the UI if a background fetch never finishes."""
        self._fetch_watchdog_id = None
        if not self._fetch_active:
            return
        self._fetch_active = False
        self._fetch_gen += 1  # ignore any late result from the stuck thread
        self.url_bar.set_ready()
        log.error(
            f"Fetch watchdog fired after {self.FETCH_TIMEOUT_MS // 1000}s "
            "without a result"
        )
        self._show_error("Fetch timed out. Check your connection and try again.")

    def _display_metadata(self, data: dict):
        """Show fetched metadata and format selector."""
        self._hide_download_result()
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
            automatic_captions=data.get("automatic_captions", []),
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

        self._hide_download_result()
        selections = self.format_selector.get_selections()
        download_mode = selections.get("download_mode", DOWNLOAD_MODE_VIDEO)
        video = self._current_metadata["video"]
        audio_formats = self._current_metadata["audio_formats"]

        video_fmt_id = None
        audio_fmt_id = None
        merge_format = None

        if download_mode == DOWNLOAD_MODE_TEXT:
            if not selections["subtitle_lang"] and not selections.get("text_track"):
                self._show_error(
                    "Select a subtitle or a transcript in the Subtitles tab "
                    "before downloading text only."
                )
                return
        elif download_mode == DOWNLOAD_MODE_AUDIO:
            audio_mode = selections.get("audio_mode", "auto")
            chosen_audio = selections.get("audio_format")
            audio_fmt_id = (
                chosen_audio if audio_mode == "format" and chosen_audio
                else resolve_best_audio_format_id(audio_formats)
            )
            if not audio_fmt_id:
                self._show_error("This video has no separate audio track to download.")
                return
        else:
            video_fmt_id = selections["video_format"]
            if not video_fmt_id:
                self._show_error("Please select a video format.")
                return
            all_video_formats = (
                self._current_metadata["video_formats"]
                + self._current_metadata["combined_formats"]
            )
            selected_video = video_format_by_id(all_video_formats, video_fmt_id)
            if selected_video is None:
                self._show_error("The selected video format is no longer available. Fetch the video again.")
                return
            audio_fmt_id = resolve_audio_format_id(
                selected_video,
                selections.get("audio_mode", "auto"),
                selections.get("audio_format"),
                audio_formats,
            )
            selected_audio = audio_format_by_id(audio_formats, audio_fmt_id)
            merge_format = resolve_merge_format(selected_video, selected_audio)

        folder_name = self.sm.create_session(video.id, video.title, video.url)
        self._pending_session_folder = folder_name
        output_dir = str(self.sm.session_dir(folder_name))
        log.info(
            f"Download session [{download_mode}]: '{folder_name}' -> {output_dir} "
            f"(video={video_fmt_id}, audio={audio_fmt_id})"
        )

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
                audio_format_id=audio_fmt_id,
                subtitle_lang=selections["subtitle_lang"],
                merge_output_format=merge_format,
                text_track=selections.get("text_track"),
                embed_subs=False,
                download_mode=download_mode,
            )

            if self._dl_cancel_event.is_set():
                self.after(0, lambda: self._status("🚫 Download cancelled"))
                self.after(0, lambda: self.dl_cancel_btn.configure(state="disabled"))
                self.after(0, lambda: self.download_btn.configure(state="normal", text="⬇ Download"))
                self._discard_session_folder(folder_name)
                return

            if result == 0:
                downloaded = self._find_result_file(output_dir, download_mode)
                if downloaded:
                    subtitle_file = self._find_subtitle_file(output_dir)
                    rec = SessionRecord(
                        video_id=video.id, title=video.title, url=video.url,
                        downloaded_file=downloaded, video_format=video_fmt_id or "",
                        subtitles_file=subtitle_file,
                        audio_format=audio_fmt_id or "",
                    )
                    self.sm.record_download(folder_name, rec)
                    self._pending_session_folder = folder_name
                    self.after(0, lambda: self._status(
                        f"✅ Downloaded: {os.path.basename(downloaded)}"
                    ))
                    self.after(0, lambda name=os.path.basename(downloaded), folder=folder_name: self._show_download_success(name, folder))
                else:
                    self._discard_session_folder(folder_name)
                    self.after(0, lambda: self._status("❌ Download failed: no output file was found"))
                    self.after(0, lambda: self._show_download_failure(
                        "The download engine completed without producing an output file."
                    ))
            else:
                self._discard_session_folder(folder_name)
                error_detail = engine.last_download_error
                self.after(0, lambda: self._status("❌ Download failed"))
                self.after(0, lambda detail=error_detail: self._show_download_failure(
                    f"{detail}\n\nCheck the log file for the full details."
                ))

            self.after(0, lambda: self.dl_cancel_btn.configure(state="disabled"))
            self.after(0, lambda: self.download_btn.configure(state="normal", text="⬇ Download"))

        Thread(target=download, daemon=True).start()

    def _on_dl_cancel(self):
        """Cancel the current download."""
        self._dl_cancel_event.set()
        self.dl_cancel_btn.configure(state="disabled")
        self._status("Cancelling download...")

    def _discard_session_folder(self, folder_name: str):
        """Remove a failed/cancelled download's folder so its name stays free.

        Called from the download thread; the UI state update is marshalled
        back to the main thread with self.after.
        """
        self.sm.discard_session(folder_name)
        self.after(0, lambda: setattr(self, "_pending_session_folder", ""))

    def _find_result_file(self, directory: str, download_mode: str) -> str:
        """Return the artifact that represents this download.

        A text-only download produces no media file, so its subtitle sidecar
        is the result rather than a sign of failure.
        """
        if download_mode == DOWNLOAD_MODE_TEXT:
            return self._find_subtitle_file(directory)
        return self._find_downloaded(directory)

    def _find_downloaded(self, directory: str) -> str:
        files = glob.glob(os.path.join(directory, "*"))
        sidecar_exts = {".vtt", ".srt", ".ass", ".lrc", ".json", ".part", ".ytdl"}
        files = [
            f for f in files
            if os.path.isfile(f) and os.path.splitext(f)[1].lower() not in sidecar_exts
        ]
        if not files:
            return ""
        return max(files, key=os.path.getctime)

    def _find_subtitle_file(self, directory: str) -> str:
        files = [
            f for f in glob.glob(os.path.join(directory, "*"))
            if os.path.isfile(f) and os.path.splitext(f)[1].lower() in {".vtt", ".srt", ".ass"}
        ]
        return max(files, key=os.path.getctime) if files else ""

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
        if current != "Download":
            self._hide_download_result()
        if current == "Convert":
            self.convert_panel.on_tab_activated()
        elif current == "Extract Audio":
            self.audio_panel.on_tab_activated()

    def _go_to_convert_tab(self):
        """Switch to Convert tab (called from download complete button)."""
        self._hide_download_result()
        self.tabview.set("Convert")
        self.convert_panel.on_tab_activated()
        pending_folder = getattr(self, "_pending_session_folder", "")
        if pending_folder:
            self.after(50, lambda folder=pending_folder: self.convert_panel.select_session(folder))

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

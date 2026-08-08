"""Convert tab: session list + transcode controls with GPU encoder selection."""
import os
import logging
import tempfile
import threading
import customtkinter as ctk
from threading import Thread
from PIL import Image
from src.gui.session_list import SessionList
from src.core.transcoder import Transcoder

log = logging.getLogger("protube")


class ConvertPanel(ctk.CTkFrame):
    """Convert tab: left session list, right transcode options + preview."""

    def __init__(self, master, session_manager, ffmpeg_manager, **kwargs):
        super().__init__(master, **kwargs)
        self.sm = session_manager
        self.ffmpeg = ffmpeg_manager
        self.transcoder = Transcoder(ffmpeg_manager)
        self._current_folder: str = ""
        self._current_file: str = ""
        self._source_bitrate: int = 0
        self._thumbnail_label: ctk.CTkLabel | None = None
        self._thumbnail_img = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left: session list
        self.session_list = SessionList(
            self, on_select=self._on_session_select, width=260,
        )
        self.session_list.grid(row=0, column=0, sticky="ns", padx=(5, 0), pady=5)

        # Right panel
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=10, pady=5)
        right.grid_columnconfigure(0, weight=1)

        # ── Preview area ───────────────────────────────────────
        self.preview_frame = ctk.CTkFrame(right, height=180, fg_color="#111")
        self.preview_frame.pack(fill="x", padx=5, pady=(10, 5))
        self.preview_frame.pack_propagate(False)

        self.preview_label = ctk.CTkLabel(
            self.preview_frame, text="🎬 Select a session to preview",
            font=ctk.CTkFont(size=13), text_color="#666",
        )
        self.preview_label.pack(expand=True)

        play_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        self.play_btn = ctk.CTkButton(
            play_frame, text="▶ Play in Default Player",
            font=ctk.CTkFont(size=12), width=180, height=30,
            command=self._on_play, fg_color="#333", hover_color="#555",
        )

        # ── File info ──────────────────────────────────────────
        self.file_info = ctk.CTkLabel(
            right, text="", font=ctk.CTkFont(size=11), text_color="#888",
        )
        self.file_info.pack(anchor="w", pady=(5, 10))

        # ── Device selection ───────────────────────────────────
        dev_frame = ctk.CTkFrame(right, fg_color="transparent")
        dev_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(dev_frame, text="Device:", font=ctk.CTkFont(size=13),
                     ).pack(side="left", padx=(0, 8))
        self.device_var = ctk.StringVar(value="cpu")
        self.device_menu = ctk.CTkOptionMenu(
            dev_frame, values=["CPU (Software)"], variable=self.device_var,
            width=150, command=self._on_device_changed,
        )
        self.device_menu.pack(side="left")

        # ── Codec selection ────────────────────────────────────
        codec_frame = ctk.CTkFrame(right, fg_color="transparent")
        codec_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(codec_frame, text="Codec:", font=ctk.CTkFont(size=13),
                     ).pack(side="left", padx=(0, 8))
        self.codec_var = ctk.StringVar(value="h264")
        self.codec_menu = ctk.CTkOptionMenu(
            codec_frame, values=["H.264 (AVC)", "H.265 (HEVC)", "AV1"],
            variable=self.codec_var, width=150,
        )
        self.codec_menu.pack(side="left")

        self._encoder_map = {}
        self._populate_device_menu()

        # ── Format ─────────────────────────────────────────────
        fmt_frame = ctk.CTkFrame(right, fg_color="transparent")
        fmt_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(fmt_frame, text="Format:", font=ctk.CTkFont(size=13),
                     ).pack(side="left", padx=(0, 8))
        self.format_var = ctk.StringVar(value="mp4")
        self.format_menu = ctk.CTkOptionMenu(
            fmt_frame, values=["mp4", "mkv", "avi", "webm", "mov"],
            variable=self.format_var, width=100,
        )
        self.format_menu.pack(side="left")

        # ── Bitrate (validated number entry) ───────────────────
        br_frame = ctk.CTkFrame(right, fg_color="transparent")
        br_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(br_frame, text="Bitrate:", font=ctk.CTkFont(size=13),
                     ).pack(side="left", padx=(0, 8))

        self.bitrate_svar = ctk.StringVar(value="")
        self.bitrate_entry = ctk.CTkEntry(
            br_frame, width=75, height=28, placeholder_text="auto",
            font=ctk.CTkFont(size=12), textvariable=self.bitrate_svar,
        )
        self.bitrate_entry.pack(side="left", padx=(0, 5))
        # Validate: only digits and single dot
        self._bitrate_valid = True
        self.bitrate_svar.trace_add("write", self._validate_bitrate)

        self.bitrate_unit_var = ctk.StringVar(value="Original")
        self.bitrate_unit_menu = ctk.CTkOptionMenu(
            br_frame, values=["Original", "Mbps", "Kbps"],
            variable=self.bitrate_unit_var, width=75,
            command=self._on_bitrate_unit_changed,
        )
        self.bitrate_unit_menu.pack(side="left")

        # Initial state: Original = readonly
        self._on_bitrate_unit_changed("Original")

        # ── Convert + Cancel buttons ────────────────────────────
        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(fill="x", pady=(15, 5))
        btn_row.grid_columnconfigure(0, weight=1)

        self.convert_btn = ctk.CTkButton(
            btn_row, text="▶ Convert", font=ctk.CTkFont(size=14, weight="bold"),
            height=42, fg_color="#1a73e8", command=self._on_convert,
        )
        self.convert_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        self.cancel_btn = ctk.CTkButton(
            btn_row, text="Cancel", font=ctk.CTkFont(size=12),
            height=42, width=80, fg_color="#c62828", hover_color="#b71c1c",
            command=self._on_cancel, state="disabled",
        )
        self.cancel_btn.grid(row=0, column=1)

        # ── Progress ───────────────────────────────────────────
        self.progress_bar = ctk.CTkProgressBar(right, height=12)
        self.progress_label = ctk.CTkLabel(
            right, text="", font=ctk.CTkFont(size=11),
        )
        self.done_label = ctk.CTkLabel(
            right, text="", font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#4caf50",
        )

    # ── bitrate validation ────────────────────────────────────

    def _validate_bitrate(self, *_):
        """Only allow digits and at most one decimal dot."""
        val = self.bitrate_svar.get()
        # Filter to allowed chars
        cleaned = "".join(c for c in val if c.isdigit() or c == ".")
        # Ensure only one dot
        if cleaned.count(".") > 1:
            dot_idx = cleaned.index(".") + 1
            cleaned = cleaned[:dot_idx] + cleaned[dot_idx:].replace(".", "")
        if cleaned != val:
            self._bitrate_valid = False
            self.bitrate_svar.set(cleaned)
        else:
            self._bitrate_valid = True

    def _on_bitrate_unit_changed(self, unit: str):
        """Enable/disable bitrate entry based on unit."""
        if unit == "Original":
            # Reset to detected source bitrate
            mbps = self._source_bitrate / 1_000_000 if self._source_bitrate else 0
            self.bitrate_entry.configure(state="normal")
            self.bitrate_entry.delete(0, "end")
            if mbps > 0:
                self.bitrate_entry.insert(0, f"{mbps:.1f}")
            self.bitrate_entry.configure(state="disabled")
        else:
            self.bitrate_entry.configure(state="normal")

    # ── device menu ────────────────────────────────────────────

    def _populate_device_menu(self):
        encoders = self.ffmpeg.get_available_encoders()
        values = []
        self._encoder_map = {}
        for e in encoders:
            values.append(e["label"])
            self._encoder_map[e["device"]] = e["encoders"]
        self.device_menu.configure(values=values)
        self.device_var.set(values[0])
        self._on_device_changed(values[0])

    def _on_device_changed(self, selection: str):
        for dev, encs in self._encoder_map.items():
            for l in self.ffmpeg.get_available_encoders():
                if l["device"] == dev and l["label"] == selection:
                    codec_labels = []
                    for ck in ["h264", "hevc", "av1"]:
                        if ck in encs:
                            codec_labels.append(self.ffmpeg.CODEC_LABELS.get(ck, ck))
                    if codec_labels:
                        self.codec_menu.configure(values=codec_labels)
                        self.codec_var.set(codec_labels[0])
                    return

    def _get_selected_encoder(self) -> tuple[str, str]:
        device_label = self.device_var.get()
        codec_label = self.codec_var.get()
        device_key = "cpu"
        for dev in self._encoder_map:
            for l in self.ffmpeg.get_available_encoders():
                if l["device"] == dev and l["label"] == device_label:
                    device_key = dev
                    break
        codec_key = "h264"
        for ck, cl in self.ffmpeg.CODEC_LABELS.items():
            if cl == codec_label:
                codec_key = ck
                break
        encoder = self._encoder_map.get(device_key, {}).get(codec_key, "libx264")
        return encoder, device_key

    # ── session logic ──────────────────────────────────────────

    def refresh_sessions(self):
        sessions = self.sm.list_sessions()
        log.info(f"ConvertPanel refresh: {len(sessions)} session(s)")
        self.session_list.populate(sessions)
        self._populate_device_menu()

    def on_tab_activated(self):
        self.refresh_sessions()

    def _on_session_select(self, folder_name: str):
        self._current_folder = folder_name
        self._clear_preview()
        rec = self.sm.get_record(folder_name)
        if rec and os.path.exists(rec.downloaded_file):
            self._current_file = rec.downloaded_file
            fname = os.path.basename(rec.downloaded_file)
            fsize = os.path.getsize(rec.downloaded_file) / (1024 * 1024)
            info = self.transcoder.get_video_info(rec.downloaded_file)
            res = ""
            source_br = 0
            if info:
                vs = next((s for s in info.get("streams", [])
                           if s.get("codec_type") == "video"), {})
                w = vs.get("width", "")
                h = vs.get("height", "")
                if w and h:
                    res = f" {w}x{h}"
                br_str = vs.get("bit_rate") or info.get("format", {}).get("bit_rate", "0")
                try:
                    source_br = int(float(br_str))
                except (ValueError, TypeError):
                    source_br = 0
            self._source_bitrate = source_br
            mbps = source_br / 1_000_000 if source_br else 0
            self.file_info.configure(
                text=f"📄 {fname}{res} ({fsize:.1f} MB)"
                + (f" | Source: {mbps:.1f} Mbps" if mbps > 0 else "")
            )
            # Set bitrate entry (readonly when Original)
            self.bitrate_entry.configure(state="normal")
            self.bitrate_entry.delete(0, "end")
            if mbps > 0:
                self.bitrate_entry.insert(0, f"{mbps:.1f}")
            # Go back to Original mode (readonly)
            if self.bitrate_unit_var.get() == "Original":
                self.bitrate_entry.configure(state="disabled")
            self.convert_btn.configure(state="normal")
            self._load_thumbnail(rec.downloaded_file, fname, fsize, res)
            self.play_btn.pack(side="bottom", pady=(0, 10))
        else:
            self._current_file = ""
            self._source_bitrate = 0
            self.file_info.configure(text="⚠ File not found")
            self.convert_btn.configure(state="disabled")
            self.play_btn.pack_forget()

    def _clear_preview(self):
        """Remove thumbnail and reset preview area."""
        if self._thumbnail_label:
            self._thumbnail_label.destroy()
            self._thumbnail_label = None
        self.preview_label.configure(text="🎬 Select a session to preview")
        if not self.preview_label.winfo_ismapped():
            self.preview_label.pack(expand=True)

    def _load_thumbnail(self, filepath: str, fname: str, fsize: float, res: str):
        """Extract a thumbnail frame using ffmpeg and display it."""
        def run():
            try:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    thumb_path = tmp.name
                cmd = [
                    self.ffmpeg.ffmpeg_path, "-y",
                    "-ss", "00:00:02",  # 2 seconds in
                    "-i", filepath,
                    "-vframes", "1",
                    "-q:v", "3",
                    "-vf", "scale=320:-1",
                    thumb_path,
                ]
                exit_code, _, _ = self.ffmpeg._run_simple(cmd, timeout=15)
                if exit_code == 0 and os.path.exists(thumb_path):
                    img = Image.open(thumb_path)
                    w, h = img.size
                    # Fit in preview area (max 320x170)
                    ctk_img = ctk.CTkImage(
                        light_image=img, dark_image=img, size=(w, h),
                    )
                    self.after(0, lambda: self._set_thumbnail(ctk_img))
                    os.unlink(thumb_path)
                else:
                    self.after(0, lambda: self.preview_label.configure(
                        text=f"📹 {fname[:50]}\n{fsize:.1f} MB{res}")
                    )
            except Exception:
                pass
        Thread(target=run, daemon=True).start()

    def _set_thumbnail(self, ctk_img):
        self.preview_label.pack_forget()
        if self._thumbnail_label:
            self._thumbnail_label.destroy()
        self._thumbnail_label = ctk.CTkLabel(
            self.preview_frame, image=ctk_img, text="",
        )
        self._thumbnail_label.pack(expand=True)

    # ── actions ────────────────────────────────────────────────

    def _on_play(self):
        if self._current_file and os.path.exists(self._current_file):
            os.startfile(self._current_file)

    def _on_convert(self):
        if not self._current_file:
            return

        fmt = self.format_var.get()

        unit = self.bitrate_unit_var.get()
        bitrate = ""
        if unit == "Original":
            if self._source_bitrate:
                bitrate = f"{int(self._source_bitrate)}"
        elif unit == "Mbps":
            val = self.bitrate_entry.get().strip()
            if val:
                bitrate = f"{val}M"
        elif unit == "Kbps":
            val = self.bitrate_entry.get().strip()
            if val:
                bitrate = f"{val}k"

        encoder, gpu_device = self._get_selected_encoder()

        base = os.path.splitext(self._current_file)[0]
        output = f"{base}_converted.{fmt}"

        self.done_label.configure(text="")
        self.convert_btn.configure(state="disabled", text="Converting...")
        self.cancel_btn.configure(state="normal")
        self.progress_bar.pack(fill="x", padx=5, pady=5)
        self.progress_bar.set(0)
        self.progress_label.pack(anchor="w", padx=5, pady=(0, 5))

        self._cancel_event = threading.Event()

        def run():
            def on_progress(pct: float, msg: str):
                self.after(0, lambda: self._update_progress(pct, msg))

            success = self.transcoder.transcode(
                input_path=self._current_file,
                output_path=output,
                video_codec=encoder,
                video_bitrate=bitrate,
                gpu_device="" if gpu_device == "cpu" else gpu_device,
                progress_callback=on_progress,
                cancel_event=self._cancel_event,
            )
            self.after(0, lambda: self._on_done(success, output))

        Thread(target=run, daemon=True).start()

    def _on_cancel(self):
        """Cancel the current conversion."""
        if hasattr(self, "_cancel_event"):
            self._cancel_event.set()
        self.cancel_btn.configure(state="disabled")
        self.progress_label.configure(text="Cancelling...")

    def _update_progress(self, pct: float, msg: str):
        self.progress_bar.set(pct / 100)
        self.progress_label.configure(text=msg)

    def _on_done(self, success: bool, output_path: str):
        self.cancel_btn.configure(state="disabled")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="")
        self.progress_bar.pack_forget()
        self.progress_label.pack_forget()
        if hasattr(self, "_cancel_event") and self._cancel_event.is_set():
            self.done_label.configure(
                text="🚫 Cancelled", text_color="#ff9800",
            )
        elif success:
            fname = os.path.basename(output_path)
            self.done_label.configure(
                text=f"✅ Conversion Complete: {fname}", text_color="#4caf50",
            )
        else:
            self.done_label.configure(
                text="❌ Conversion Failed", text_color="#ff4d4d",
            )
        self.done_label.pack(anchor="w", padx=5, pady=(0, 10))
        self.convert_btn.configure(state="normal", text="▶ Convert")

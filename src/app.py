"""ProTube application controller."""
import os
import logging
import customtkinter as ctk
from src.utils.ffmpeg import FFmpegManager
from src.utils.logging_setup import setup_logging
from src.gui.main_window import MainWindow

log = logging.getLogger("protube")


class ProTubeApp:
    """Main application class. Sets up window, theme, and FFmpeg check."""

    APP_NAME = "ProTube"
    APP_VERSION = "0.2.0"
    WINDOW_WIDTH = 1100
    WINDOW_HEIGHT = 750

    def __init__(self):
        self.ffmpeg = FFmpegManager()

        # Setup logging first (needs to know base dir for log files)
        from src.core.session_manager import SessionManager
        temp_sm = SessionManager()
        self.logger = setup_logging(temp_sm.base_dir)
        log.info(f"ProTube v{self.APP_VERSION} initializing")

        # Configure customtkinter
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title(f"{self.APP_NAME} v{self.APP_VERSION}")
        self.root.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.root.minsize(900, 600)

        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.WINDOW_WIDTH // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.WINDOW_HEIGHT // 2)
        self.root.geometry(f"+{x}+{y}")

        # Set window icon
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

        # Set up UI
        self.main_window = MainWindow(self.root, self.ffmpeg)
        self.main_window.pack(fill="both", expand=True)

        # Check FFmpeg after UI is ready
        self.root.after(500, self._check_ffmpeg)

    def _check_ffmpeg(self):
        """Check FFmpeg availability; prompt download if missing."""
        if not self.ffmpeg.available:
            self._show_ffmpeg_dialog()

    def _show_ffmpeg_dialog(self):
        """Show a dialog to download FFmpeg."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("FFmpeg Required")
        dialog.geometry("450x220")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() // 2) - 225
        py = self.root.winfo_y() + (self.root.winfo_height() // 2) - 110
        dialog.geometry(f"+{px}+{py}")

        ctk.CTkLabel(
            dialog,
            text="FFmpeg Required",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            dialog,
            text="FFmpeg is needed for video processing\n"
                 "(transcoding, subtitle embedding, audio extraction).\n"
                 "Download now? (~50 MB)",
            font=ctk.CTkFont(size=13),
            justify="center",
        ).pack(pady=10)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)

        def download():
            btn.configure(text="Downloading...", state="disabled")
            skip_btn.configure(state="disabled")
            dialog.update()

            def on_progress(pct, msg):
                status_label.configure(text=msg)
                dialog.update()

            success = self.ffmpeg.download_ffmpeg(progress_callback=on_progress)
            if success:
                dialog.destroy()
            else:
                status_label.configure(text="Download failed. Check your internet connection.")
                btn.configure(text="Retry", state="normal")
                skip_btn.configure(state="normal")

        status_label = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=11))
        status_label.pack(pady=(0, 5))

        btn = ctk.CTkButton(
            btn_frame, text="Download FFmpeg",
            command=download, width=160,
        )
        btn.pack(side="left", padx=5)

        skip_btn = ctk.CTkButton(
            btn_frame, text="Skip (limited functionality)",
            fg_color="transparent", command=dialog.destroy, width=160,
        )
        skip_btn.pack(side="left", padx=5)

    def run(self):
        self.root.mainloop()

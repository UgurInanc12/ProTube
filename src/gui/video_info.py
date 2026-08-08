"""Video metadata display panel with thumbnail."""
import customtkinter as ctk
from threading import Thread
from io import BytesIO
import requests
from PIL import Image
from src.core.models import VideoInfo


class VideoInfoPanel(ctk.CTkFrame):
    """Displays video metadata: thumbnail, title, channel, duration, views."""

    THUMB_WIDTH = 240
    THUMB_HEIGHT = 135

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._thumbnail_ctk_img = None
        self._thumbnail_label = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        # Thumbnail frame (left side)
        self.thumb_frame = ctk.CTkFrame(
            self, width=self.THUMB_WIDTH, height=self.THUMB_HEIGHT
        )
        self.thumb_frame.grid(
            row=0, column=0, rowspan=4, padx=10, pady=10, sticky="nw"
        )
        self.thumb_frame.pack_propagate(False)

        self.thumb_placeholder = ctk.CTkLabel(
            self.thumb_frame,
            text="🎬\nNo video loaded",
            font=ctk.CTkFont(size=16),
            width=self.THUMB_WIDTH,
            height=self.THUMB_HEIGHT,
        )
        self.thumb_placeholder.pack(expand=True)

        # Info labels (right side)
        self.title_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=16, weight="bold"),
            wraplength=550,
            anchor="w",
            justify="left",
        )
        self.title_label.grid(
            row=0, column=1, padx=(5, 10), pady=(10, 2), sticky="w"
        )

        self.channel_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.channel_label.grid(
            row=1, column=1, padx=(5, 10), pady=2, sticky="w"
        )

        # Meta bar: duration, views, date
        self.meta_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.meta_frame.grid(
            row=2, column=1, padx=(5, 10), pady=5, sticky="w"
        )

        self.duration_label = ctk.CTkLabel(
            self.meta_frame, text="", font=ctk.CTkFont(size=12),
        )
        self.duration_label.pack(side="left", padx=(0, 15))

        self.views_label = ctk.CTkLabel(
            self.meta_frame, text="", font=ctk.CTkFont(size=12),
        )
        self.views_label.pack(side="left", padx=(0, 15))

        self.date_label = ctk.CTkLabel(
            self.meta_frame, text="", font=ctk.CTkFont(size=12),
        )
        self.date_label.pack(side="left")

    def update_info(self, video: VideoInfo):
        """Update displayed video information."""
        self.title_label.configure(text=video.title)
        self.channel_label.configure(text=video.channel)
        self.duration_label.configure(text=f"⏱ {video.duration_formatted}")

        if video.view_count:
            count = video.view_count
            if count >= 1_000_000:
                views = f"{count / 1_000_000:.1f}M"
            elif count >= 1_000:
                views = f"{count / 1_000:.1f}K"
            else:
                views = str(count)
            self.views_label.configure(text=f"👁 {views} views")

        if video.upload_date and len(video.upload_date) == 8:
            date = video.upload_date
            formatted = f"{date[6:8]}.{date[4:6]}.{date[:4]}"
            self.date_label.configure(text=f"📅 {formatted}")

        # Load thumbnail in background
        if video.thumbnail_url:
            Thread(
                target=self._load_thumbnail,
                args=(video.thumbnail_url,),
                daemon=True,
            ).start()

    def _load_thumbnail(self, url: str):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            img = img.resize(
                (self.THUMB_WIDTH, self.THUMB_HEIGHT), Image.Resampling.LANCZOS
            )
            self._thumbnail_ctk_img = ctk.CTkImage(
                light_image=img, dark_image=img,
                size=(self.THUMB_WIDTH, self.THUMB_HEIGHT),
            )
            # Must update from main thread
            self.after(0, self._set_thumbnail)
        except Exception:
            pass

    def _set_thumbnail(self):
        if self._thumbnail_label is None:
            self.thumb_placeholder.destroy()
            self._thumbnail_label = ctk.CTkLabel(
                self.thumb_frame, image=self._thumbnail_ctk_img, text=""
            )
            self._thumbnail_label.pack(expand=True)
        else:
            self._thumbnail_label.configure(image=self._thumbnail_ctk_img)

    def clear(self):
        """Clear all displayed information."""
        self.title_label.configure(text="")
        self.channel_label.configure(text="")
        self.duration_label.configure(text="")
        self.views_label.configure(text="")
        self.date_label.configure(text="")
        if self._thumbnail_label:
            self._thumbnail_label.destroy()
            self._thumbnail_label = None
            self.thumb_placeholder = ctk.CTkLabel(
                self.thumb_frame,
                text="🎬\nNo video loaded",
                font=ctk.CTkFont(size=16),
                width=self.THUMB_WIDTH,
                height=self.THUMB_HEIGHT,
            )
            self.thumb_placeholder.pack(expand=True)

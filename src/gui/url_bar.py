"""URL input bar with fetch button."""
import customtkinter as ctk
from typing import Callable


class URLBar(ctk.CTkFrame):
    """Input bar for YouTube URL with fetch button."""

    def __init__(self, master, on_fetch: Callable[[str], None], **kwargs):
        super().__init__(master, **kwargs)
        self.on_fetch = on_fetch
        self._is_loading = False
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        self.url_var = ctk.StringVar()
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="Paste YouTube URL here... (Ctrl+V)",
            height=44,
            font=ctk.CTkFont(size=14),
            textvariable=self.url_var,
        )
        self.entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
        self.entry.bind("<Return>", lambda e: self._fetch())

        self.fetch_btn = ctk.CTkButton(
            self,
            text="Fetch",
            width=110,
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._fetch,
        )
        self.fetch_btn.grid(row=0, column=1, padx=(5, 10), pady=10)

    def _fetch(self):
        url = self.url_var.get().strip()
        if url and not self._is_loading:
            self._is_loading = True
            self.fetch_btn.configure(text="Loading...", state="disabled")
            self.on_fetch(url)

    def set_ready(self):
        self._is_loading = False
        self.fetch_btn.configure(text="Fetch", state="normal")

    def set_url(self, url: str):
        self.url_var.set(url)

    def clear(self):
        self.url_var.set("")
        self.set_ready()

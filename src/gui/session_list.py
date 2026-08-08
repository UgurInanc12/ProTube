"""Reusable session list sidebar widget with double-click support."""
import os
import subprocess
import customtkinter as ctk
from typing import Callable, Optional


class SessionList(ctk.CTkScrollableFrame):
    """Scrollable list of downloaded video sessions."""

    def __init__(self, master, on_select: Callable[[str], None],
                 on_double_click: Optional[Callable[[str], None]] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_select = on_select
        self.on_double_click = on_double_click
        self._selected: Optional[str] = None
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._widgets: list = []

    def populate(self, sessions: list[dict]):
        """Populate the list. Each dict: {folder_name, title, downloaded_file, ...}"""
        for w in self._widgets:
            w.destroy()
        self._widgets.clear()
        self._buttons.clear()
        self._selected = None

        if not sessions:
            lbl = ctk.CTkLabel(
                self, text="No sessions yet.\nDownload a video first!",
                font=ctk.CTkFont(size=13), text_color="gray",
            )
            lbl.pack(pady=30, padx=10)
            self._widgets.append(lbl)
            return

        header = ctk.CTkLabel(
            self, text=f"Sessions ({len(sessions)})",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        header.pack(anchor="w", padx=8, pady=(5, 5))
        self._widgets.append(header)

        for session in sessions:
            folder = session["folder_name"]
            title = session["title"]
            file_exists = bool(session.get("downloaded_file"))
            file_path = session.get("downloaded_file", "")

            display = title[:60] + "..." if len(title) > 60 else title

            btn = ctk.CTkButton(
                self,
                text=f"{'📁' if file_exists else '⚠'} {display}",
                anchor="w",
                fg_color="transparent",
                hover_color="#333333",
                font=ctk.CTkFont(size=12),
                height=36,
                command=lambda f=folder: self._select(f),
            )
            # Double-click: open in Explorer
            btn.bind("<Double-Button-1>", lambda e, fp=file_path, dn=folder:
                     self._open_in_explorer(fp, dn))
            btn.pack(fill="x", padx=5, pady=2)
            self._buttons[folder] = btn
            self._widgets.append(btn)

    def _select(self, folder_name: str):
        if self._selected and self._selected in self._buttons:
            self._buttons[self._selected].configure(fg_color="transparent")
        self._selected = folder_name
        if folder_name in self._buttons:
            self._buttons[folder_name].configure(fg_color="#1a73e8")
        self.on_select(folder_name)

    def select(self, folder_name: str):
        """Programmatically select a visible session."""
        if folder_name in self._buttons:
            self._select(folder_name)

    def _open_in_explorer(self, file_path: str, folder_name: str):
        """Open the session folder or file location in Windows Explorer."""
        if file_path and os.path.exists(file_path):
            subprocess.Popen(["explorer", "/select,", file_path])
        elif self.on_double_click:
            self.on_double_click(folder_name)

    def get_selected(self) -> Optional[str]:
        return self._selected

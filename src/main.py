"""ProTube -- Professional YouTube Video Downloader.

Entry point for the desktop application.
"""
import sys
import os
import tkinter as tk


def main():
    # Handle high-DPI displays on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    # Add src to path for PyInstaller compatibility
    if getattr(sys, "frozen", False):
        os.chdir(os.path.dirname(sys.executable))

    from src.app import ProTubeApp

    app = ProTubeApp()
    app.run()


if __name__ == "__main__":
    main()

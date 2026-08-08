"""Build script for ProTube single EXE.

Usage:
    python build.py

Output: dist/ProTube.exe
"""
import os
import sys
import subprocess
import shutil


APP_NAME = "ProTube"
ENTRY_POINT = "src/main.py"
ICON_PATH = "assets/icon.ico"


def clean():
    """Remove previous build artifacts."""
    for d in ["build", "dist"]:
        if os.path.exists(d):
            shutil.rmtree(d)
    for f in os.listdir("."):
        if f.endswith(".spec"):
            os.remove(f)


def build():
    """Build the single EXE with PyInstaller."""
    print("=" * 60)
    print(f"Building {APP_NAME}...")
    print("=" * 60)

    clean()

    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--clean",
        "--noconfirm",
        "--hidden-import", "yt_dlp",
        "--hidden-import", "yt_dlp.extractor",
        "--hidden-import", "yt_dlp.downloader",
        "--hidden-import", "yt_dlp.postprocessor",
        "--hidden-import", "customtkinter",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "darkdetect",
        "--hidden-import", "requests",
        "--collect-all", "customtkinter",
        ENTRY_POINT,
    ]

    # Add icon if exists
    if os.path.exists(ICON_PATH):
        cmd.insert(-1, f"--icon={ICON_PATH}")

    print(f"Running: {' '.join(cmd[:10])} ...")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\n❌ Build failed!")
        return False

    # Verify output
    dist_exe = os.path.join("dist", f"{APP_NAME}.exe")
    if os.path.exists(dist_exe):
        size_mb = os.path.getsize(dist_exe) / (1024 * 1024)
        print(f"\n{'=' * 60}")
        print(f"✅ Build successful!")
        print(f"   Output: {os.path.abspath(dist_exe)}")
        print(f"   Size: {size_mb:.1f} MB")
        print(f"{'=' * 60}")
        return True
    else:
        print(f"\n❌ Build failed: {dist_exe} not found")
        return False


if __name__ == "__main__":
    build()

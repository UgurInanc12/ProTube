# ProTube

Professional YouTube video downloader with a modern desktop GUI.

Single EXE, no installation required. Download videos, convert formats, extract audio.

## Features

- **Download**: Paste any YouTube URL, see all available formats (resolution, FPS, codec, filesize), pick your quality, download
- **Convert**: Transcode downloaded videos to MP4, MKV, AVI, WebM, MOV with custom bitrate. GPU acceleration (NVIDIA NVENC, AMD AMF, Intel QSV) when available
- **Extract Audio**: Pull audio tracks as MP3, AAC, WAV, OGG, M4A
- **Subtitle support**: Download and embed subtitles in any language
- **Session management**: Each download creates a session folder. Browse, convert, and extract from past downloads
- **Real progress**: FFmpeg progress parsing shows actual encoding percentage
- **Cancel support**: Stop any operation mid-process

## Requirements

- Windows 10+
- [Node.js](https://nodejs.org/) (for YouTube's JavaScript challenges, required by yt-dlp)
- [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) (auto-downloaded on first launch if not found)

## Quick Start

Download `ProTube.exe` from [Releases](../../releases), double-click to run.

## Development

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
python -m src.main
```

## Build

```bash
python build.py
# Output: dist/ProTube.exe (~50 MB)
```

## CLI Testing

```bash
python cli_test.py fetch <url>           # Fetch metadata
python cli_test.py download <url>        # Download at lowest quality
python cli_test.py convert <filepath>    # Transcode with FFmpeg
python cli_test.py audio <filepath>      # Extract audio
```

## Architecture

```
src/
  main.py                    # Entry point
  app.py                     # Application controller, theme, FFmpeg check
  core/
    engine.py                # yt-dlp wrapper with multi-strategy auth
    models.py                # Dataclasses: VideoInfo, FormatInfo, etc.
    session_manager.py       # Session persistence, file organization
    transcoder.py            # FFmpeg transcode orchestration
  gui/
    main_window.py           # Tabbed layout: Download / Convert / Audio
    url_bar.py               # URL input with fetch button
    video_info.py            # Thumbnail, title, channel, duration display
    format_selector.py       # Format selection with tabs (video/audio/subtitles)
    convert_panel.py         # Convert tab: session list + GPU/codec/bitrate controls
    audio_panel.py           # Audio tab: session list + format selection
    session_list.py          # Reusable session sidebar with double-click Explorer
    session_view.py          # Download progress + post-processing
  utils/
    ffmpeg.py                # FFmpeg discovery, auto-download, command building
    logging_setup.py         # Timestamped file logging
```

## Tech Stack

- **Python 3.11** + **customtkinter** (dark-themed modern UI)
- **yt-dlp** (YouTube download engine with multi-strategy auth)
- **FFmpeg** (video processing, auto-downloaded essentials build)
- **PyInstaller** (single EXE packaging)

## How Authentication Works

YouTube sometimes requires sign-in to verify you're not a bot. ProTube tries multiple strategies in order:

1. No authentication (works for most videos)
2. Chrome browser cookies
3. Edge browser cookies
4. `cookies.txt` file (if placed in sessions directory)

For persistent auth issues, install the "Get cookies.txt LOCALLY" Chrome extension, export cookies from youtube.com, and save to `ProTube Sessions/cookies.txt`.

## License

MIT

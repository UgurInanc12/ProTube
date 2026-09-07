"""CLI test script for ProTube engine. No GUI needed.

Usage:
    python cli_test.py fetch <url>           # fetch metadata only
    python cli_test.py download <url>        # fetch + download at lowest quality
    python cli_test.py audio-only <url>      # fetch + download best audio only
    python cli_test.py text-only <url> [lang]  # fetch + download subtitle only
    python cli_test.py convert <filepath>    # transcode with FFmpeg
    python cli_test.py audio <filepath>      # extract audio
"""
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Set up logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("protube")

from src.core.engine import VideoEngine
from src.core.download_options import (
    DOWNLOAD_MODE_AUDIO,
    DOWNLOAD_MODE_TEXT,
    audio_format_by_id,
    resolve_best_audio_format_id,
)
from src.core.session_manager import SessionManager, SessionRecord
from src.core.transcoder import Transcoder
from src.utils.ffmpeg import FFmpegManager


def cmd_fetch(url: str):
    """Fetch video metadata and display it."""
    print(f"\n=== Fetching: {url} ===\n")
    engine = VideoEngine()

    try:
        data = engine.fetch_metadata(url)
    except Exception as e:
        print(f"\nFAILED: {e}")
        return False

    video = data["video"]
    print(f"Title:     {video.title}")
    print(f"Channel:   {video.channel}")
    print(f"Duration:  {video.duration_formatted}")
    print(f"Views:     {video.view_count:,}")
    print(f"Thumbnail: {video.thumbnail_url}")

    print(f"\nVideo formats ({len(data['video_formats'])}):")
    for f in data["video_formats"][:5]:
        print(f"  {f.format_id:>6}  {f.resolution_short:>6}  {f.codec:>8}  "
              f"{f.fps or 0:.0f}fps  {f.filesize_mb or 0:.1f}MB")

    print(f"\nCombined formats ({len(data['combined_formats'])}):")
    for f in data["combined_formats"][:5]:
        print(f"  {f.format_id:>6}  {f.resolution_short:>6}  {f.codec:>8}  "
              f"{f.fps or 0:.0f}fps  {f.filesize_mb or 0:.1f}MB")

    print(f"\nAudio formats ({len(data['audio_formats'])}):")
    for f in data["audio_formats"][:3]:
        print(f"  {f.format_id:>6}  {f.abr or 0:>6.0f}kbps  {f.codec:>8}  .{f.ext}")

    print(f"\nSubtitles ({len(data['subtitles'])}):")
    for s in data["subtitles"][:5]:
        print(f"  {s.language:>4}  {s.label}")

    return data


def cmd_download(url: str):
    """Fetch metadata, pick lowest quality, and download."""
    sm = SessionManager()
    print(f"\n=== Fetching metadata ===\n")
    engine = VideoEngine()

    try:
        data = engine.fetch_metadata(url)
    except Exception as e:
        print(f"\nFETCH FAILED: {e}")
        return False

    video = data["video"]
    print(f"Title: {video.title}")

    # Pick lowest quality video format (smallest resolution)
    video_fmts = data["video_formats"] + data["combined_formats"]
    if not video_fmts:
        print("No video formats found!")
        return False

    # Sort ascending (smallest first)
    def res_key(f):
        try:
            return int(f.resolution.split("x")[1]) if f.resolution else 0
        except (IndexError, ValueError):
            return 0

    video_fmts.sort(key=res_key)
    chosen = video_fmts[0]
    print(f"Chosen format: {chosen.format_id} ({chosen.resolution_short}, "
          f"{chosen.codec}, {chosen.filesize_mb or '?'}MB)")

    # Create session
    folder_name = sm.create_session(video.id, video.title, video.url)
    output_dir = str(sm.session_dir(folder_name))
    print(f"Output dir: {output_dir}")

    # Pick audio format if video-only
    audio_fmt_id = None
    if not chosen.has_audio and data["audio_formats"]:
        audio_fmt = data["audio_formats"][0]
        audio_fmt_id = audio_fmt.format_id
        print(f"Audio format: {audio_fmt_id} ({audio_fmt.abr}kbps)")

    # Download
    print(f"\n=== Downloading ===\n")
    exit_code = engine.download(
        url=url,
        output_dir=output_dir,
        format_id=chosen.format_id,
        audio_format_id=audio_fmt_id,
    )

    if exit_code == 0:
        # Find downloaded file
        import glob
        files = [f for f in glob.glob(os.path.join(output_dir, "*"))
                 if os.path.isfile(f) and not f.endswith(".json")]
        if files:
            downloaded = max(files, key=os.path.getctime)
            size_mb = os.path.getsize(downloaded) / (1024 * 1024)
            print(f"\nSUCCESS: {os.path.basename(downloaded)} ({size_mb:.1f}MB)")

            # Record session
            rec = SessionRecord(
                video_id=video.id,
                title=video.title,
                url=video.url,
                downloaded_file=downloaded,
                video_format=chosen.format_id,
                audio_format=audio_fmt_id or "",
            )
            sm.record_download(folder_name, rec)
            print(f"Session recorded: {folder_name}")
            return downloaded
        else:
            print("\nSUCCESS but no file found in output dir")
            return True
    else:
        print(f"\nDOWNLOAD FAILED (exit code: {exit_code})")
        sm.discard_session(folder_name)
        return False


def cmd_audio_only(url: str):
    """Fetch metadata, then download the best audio track without any video."""
    sm = SessionManager()
    print("\n=== Fetching metadata ===\n")
    engine = VideoEngine()

    try:
        data = engine.fetch_metadata(url)
    except Exception as e:
        print(f"\nFETCH FAILED: {e}")
        return False

    video = data["video"]
    print(f"Title: {video.title}")

    audio_id = resolve_best_audio_format_id(data["audio_formats"])
    if not audio_id:
        print("No separate audio track is available for this video.")
        return False
    chosen = audio_format_by_id(data["audio_formats"], audio_id)
    print(
        f"Chosen audio: {chosen.format_id} ({chosen.abr}kbps, "
        f"{chosen.codec}, .{chosen.ext}, {chosen.filesize_mb or '?'}MB)"
    )

    folder_name = sm.create_session(video.id, video.title, video.url)
    output_dir = str(sm.session_dir(folder_name))
    print(f"Output dir: {output_dir}")

    print("\n=== Downloading audio only ===\n")
    exit_code = engine.download(
        url=url,
        output_dir=output_dir,
        audio_format_id=audio_id,
        download_mode=DOWNLOAD_MODE_AUDIO,
    )

    if exit_code != 0:
        print(f"\nDOWNLOAD FAILED: {engine.last_download_error}")
        sm.discard_session(folder_name)
        return False

    import glob
    files = [f for f in glob.glob(os.path.join(output_dir, "*")) if os.path.isfile(f)]
    if not files:
        print("\nSUCCESS reported but no file found")
        sm.discard_session(folder_name)
        return False

    downloaded = max(files, key=os.path.getctime)
    size_mb = os.path.getsize(downloaded) / (1024 * 1024)
    print(f"\nSUCCESS: {os.path.basename(downloaded)} ({size_mb:.1f}MB)")
    sm.record_download(folder_name, SessionRecord(
        video_id=video.id, title=video.title, url=video.url,
        downloaded_file=downloaded, audio_format=audio_id,
    ))
    return downloaded


def cmd_text_only(url: str, language: str = ""):
    """Fetch metadata, then download only a subtitle or transcript track."""
    sm = SessionManager()
    print("\n=== Fetching metadata ===\n")
    engine = VideoEngine()

    try:
        data = engine.fetch_metadata(url)
    except Exception as e:
        print(f"\nFETCH FAILED: {e}")
        return False

    video = data["video"]
    print(f"Title: {video.title}")
    print(f"Manual subtitles: {[s.language for s in data['subtitles']]}")

    subtitle_lang = None
    text_track = None
    available = {s.language: s for s in data["subtitles"]}
    if language and language in available:
        subtitle_lang = language
    elif not language and available:
        subtitle_lang = next(iter(available))
    else:
        # _parse_text_tracks puts the real ASR tracks first, so the head of the
        # list is the spoken language rather than an alphabetical translation.
        auto = data["automatic_captions"]
        if language:
            text_track = next((t for t in auto if t.language == language), None)
        elif auto:
            text_track = auto[0]

    if not subtitle_lang and not text_track:
        print("No subtitle or transcript track is available.")
        return False
    print(f"Chosen text track: {subtitle_lang or text_track.language} "
          f"({'manual subtitle' if subtitle_lang else 'auto transcript'})")

    folder_name = sm.create_session(video.id, video.title, video.url)
    output_dir = str(sm.session_dir(folder_name))
    print(f"Output dir: {output_dir}")

    print("\n=== Downloading text only ===\n")
    exit_code = engine.download(
        url=url,
        output_dir=output_dir,
        subtitle_lang=subtitle_lang,
        text_track=text_track,
        download_mode=DOWNLOAD_MODE_TEXT,
    )

    if exit_code != 0:
        print(f"\nDOWNLOAD FAILED: {engine.last_download_error}")
        sm.discard_session(folder_name)
        return False

    import glob
    files = [f for f in glob.glob(os.path.join(output_dir, "*")) if os.path.isfile(f)]
    if not files:
        print("\nSUCCESS reported but no file found")
        sm.discard_session(folder_name)
        return False

    downloaded = max(files, key=os.path.getctime)
    size_kb = os.path.getsize(downloaded) / 1024
    print(f"\nSUCCESS: {os.path.basename(downloaded)} ({size_kb:.1f}KB)")
    sm.record_download(folder_name, SessionRecord(
        video_id=video.id, title=video.title, url=video.url,
        downloaded_file=downloaded, subtitles_file=downloaded,
    ))
    return downloaded


def cmd_convert(filepath: str):
    """Test FFmpeg transcoding on a file."""
    ffmpeg = FFmpegManager()
    if not ffmpeg.available:
        print("FFmpeg not available!")
        return False

    transcoder = Transcoder(ffmpeg)
    base, ext = os.path.splitext(filepath)
    output = f"{base}_test_converted.mp4"

    print(f"Converting: {filepath}")
    print(f"Output:     {output}")

    def on_progress(pct, msg):
        print(f"\r  {msg}", end="", flush=True)

    success = transcoder.transcode(
        input_path=filepath,
        output_path=output,
        video_codec="libx264",
        video_bitrate="500k",
        crf=28,
        progress_callback=on_progress,
    )

    print()
    if success:
        size = os.path.getsize(output) / (1024 * 1024)
        print(f"SUCCESS: {os.path.basename(output)} ({size:.1f}MB)")
        return output
    else:
        print("FAILED")
        return False


def cmd_audio(filepath: str):
    """Test audio extraction on a file."""
    ffmpeg = FFmpegManager()
    if not ffmpeg.available:
        print("FFmpeg not available!")
        return False

    transcoder = Transcoder(ffmpeg)
    base, ext = os.path.splitext(filepath)
    output = f"{base}_test_audio.mp3"

    print(f"Extracting audio from: {filepath}")
    print(f"Output:                {output}")

    success = transcoder.extract_audio(filepath, output, "mp3")

    if success:
        size = os.path.getsize(output) / (1024 * 1024)
        print(f"SUCCESS: {os.path.basename(output)} ({size:.1f}MB)")
        return output
    else:
        print("FAILED")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    arg = sys.argv[2]

    if cmd == "fetch":
        result = cmd_fetch(arg)
        sys.exit(0 if result else 1)
    elif cmd == "download":
        result = cmd_download(arg)
        sys.exit(0 if result else 1)
    elif cmd == "audio-only":
        result = cmd_audio_only(arg)
        sys.exit(0 if result else 1)
    elif cmd == "text-only":
        result = cmd_text_only(arg, sys.argv[3] if len(sys.argv) > 3 else "")
        sys.exit(0 if result else 1)
    elif cmd == "convert":
        result = cmd_convert(arg)
        sys.exit(0 if result else 1)
    elif cmd == "audio":
        result = cmd_audio(arg)
        sys.exit(0 if result else 1)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

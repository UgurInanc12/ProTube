"""FFmpeg manager: discovery, download, GPU detection, and transcoding interface."""
import os
import sys
import re
import shutil
import subprocess
import zipfile
import urllib.request
from pathlib import Path
from typing import Optional, Callable


class FFmpegManager:
    """Manages FFmpeg binary discovery, GPU detection, and transcoding."""

    FFMPEG_DOWNLOAD_URL = (
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    )

    # ── encoder tables ──────────────────────────────────────────
    ENCODER_TABLE = {
        "cpu": {
            "h264": "libx264",
            "hevc": "libx265",
            "av1": "libsvtav1",
        },
        "nvidia": {
            "h264": "h264_nvenc",
            "hevc": "hevc_nvenc",
            "av1": "av1_nvenc",
        },
        "amd": {
            "h264": "h264_amf",
            "hevc": "hevc_amf",
            "av1": "av1_amf",
        },
        "intel": {
            "h264": "h264_qsv",
            "hevc": "hevc_qsv",
            "av1": "av1_qsv",
        },
    }

    CODEC_LABELS = {
        "h264": "H.264 (AVC)",
        "hevc": "H.265 (HEVC)",
        "av1": "AV1",
    }

    def __init__(self):
        self._ffmpeg_path = "ffmpeg"
        self._ffprobe_path = "ffprobe"
        self._app_data = (
            Path(os.getenv("APPDATA", os.path.expanduser("~")))
            / "ProTube"
            / "ffmpeg"
        )
        self._available = False
        self._gpu_devices: dict[str, bool] = {}  # nvidia/amd/intel -> bool
        self._discover_ffmpeg()

    # ── properties ──────────────────────────────────────────────
    @property
    def available(self) -> bool:
        return self._available

    @property
    def ffmpeg_path(self) -> str:
        return self._ffmpeg_path

    @property
    def ffprobe_path(self) -> str:
        return self._ffprobe_path

    @property
    def gpu_devices(self) -> dict[str, bool]:
        """Returns {nvidia: bool, amd: bool, intel: bool}."""
        if not self._gpu_devices:
            self._detect_gpus()
        return dict(self._gpu_devices)

    # ── discovery ───────────────────────────────────────────────

    def _discover_ffmpeg(self):
        """Find FFmpeg: bundled > app data > system PATH."""
        if getattr(sys, "frozen", False):
            bundle_dir = Path(sys._MEIPASS)
            ffmpeg_exe = bundle_dir / "ffmpeg.exe"
            ffprobe_exe = bundle_dir / "ffprobe.exe"
            if ffmpeg_exe.exists():
                self._ffmpeg_path = str(ffmpeg_exe)
                self._ffprobe_path = str(ffprobe_exe)
                self._available = True
                return

        ffmpeg_exe = self._app_data / "ffmpeg.exe"
        ffprobe_exe = self._app_data / "ffprobe.exe"
        if ffmpeg_exe.exists():
            self._ffmpeg_path = str(ffmpeg_exe)
            self._ffprobe_path = str(ffprobe_exe)
            self._available = True
            return

        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            self._ffmpeg_path = system_ffmpeg
            system_ffprobe = shutil.which("ffprobe")
            self._ffprobe_path = (
                system_ffprobe
                if system_ffprobe
                else system_ffmpeg.replace("ffmpeg", "ffprobe")
            )
            self._available = True

    def _detect_gpus(self):
        """Detect available GPU encoders via ffmpeg -encoders output."""
        self._gpu_devices = {"nvidia": False, "amd": False, "intel": False}
        if not self._available:
            return
        try:
            exit_code, stdout, _ = self._run_simple(
                [self._ffmpeg_path, "-encoders"], timeout=15
            )
            if exit_code == 0:
                output = (stdout or "").lower()
                self._gpu_devices["nvidia"] = "nvenc" in output
                self._gpu_devices["amd"] = "_amf" in output
                self._gpu_devices["intel"] = "_qsv" in output
        except Exception:
            pass

    def get_available_encoders(self) -> list[dict]:
        """Return list of available encoder options with labels."""
        if not self._gpu_devices:
            self._detect_gpus()
        options = [{"device": "cpu", "label": "CPU (Software)", "encoders": self.ENCODER_TABLE["cpu"]}]
        if self._gpu_devices.get("nvidia"):
            options.append({"device": "nvidia", "label": "NVIDIA GPU (NVENC)", "encoders": self.ENCODER_TABLE["nvidia"]})
        if self._gpu_devices.get("amd"):
            options.append({"device": "amd", "label": "AMD GPU (AMF)", "encoders": self.ENCODER_TABLE["amd"]})
        if self._gpu_devices.get("intel"):
            options.append({"device": "intel", "label": "Intel GPU (QSV)", "encoders": self.ENCODER_TABLE["intel"]})
        return options

    # ── download ────────────────────────────────────────────────

    def ensure_ffmpeg(self) -> bool:
        if self._available:
            return True
        return self.download_ffmpeg()

    def download_ffmpeg(self, progress_callback=None) -> bool:
        try:
            self._app_data.mkdir(parents=True, exist_ok=True)
            if progress_callback:
                progress_callback(0, "Downloading FFmpeg...")
            zip_path = self._app_data / "ffmpeg.zip"
            urllib.request.urlretrieve(self.FFMPEG_DOWNLOAD_URL, zip_path)
            if progress_callback:
                progress_callback(50, "Extracting FFmpeg...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    filename = os.path.basename(member)
                    if filename in ("ffmpeg.exe", "ffprobe.exe") and filename:
                        with zf.open(member) as src:
                            dest = self._app_data / filename
                            with open(dest, "wb") as dst:
                                dst.write(src.read())
            zip_path.unlink()
            if progress_callback:
                progress_callback(100, "FFmpeg ready")
            self._available = False
            self._discover_ffmpeg()
            return self._available
        except Exception as e:
            if progress_callback:
                progress_callback(-1, f"Failed: {e}")
            return False

    # ── command builders ────────────────────────────────────────

    def build_transcode_command(
        self,
        input_path: str,
        output_path: str,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        video_bitrate: str = "",
        audio_bitrate: str = "",
        crf: int = 23,
        resolution: str = "",
        fps: int = 0,
        gpu_device: str = "",
    ) -> list[str]:
        """Build an FFmpeg transcode command with optional GPU acceleration.

        Args:
            gpu_device: 'nvidia', 'amd', 'intel', or '' for software.
        """
        cmd = [self._ffmpeg_path, "-y"]

        # GPU hardware acceleration input
        hwaccel_map = {"nvidia": "cuda", "amd": "d3d11va", "intel": "qsv"}
        if gpu_device and gpu_device in hwaccel_map:
            cmd += ["-hwaccel", hwaccel_map[gpu_device]]

        cmd += ["-i", input_path]

        if video_codec:
            cmd += ["-c:v", video_codec]
        if audio_codec:
            cmd += ["-c:a", audio_codec]
        if video_bitrate:
            cmd += ["-b:v", video_bitrate]
        if audio_bitrate:
            cmd += ["-b:a", audio_bitrate]
        if crf >= 0:
            cmd += ["-crf", str(crf)]
        if resolution:
            cmd += ["-vf", f"scale={resolution}"]
        if fps > 0:
            cmd += ["-r", str(fps)]
        if output_path.endswith(".mp4"):
            cmd += ["-movflags", "+faststart"]

        cmd.append(output_path)
        return cmd

    def build_audio_extract_command(
        self, input_path: str, output_path: str, format: str = "mp3",
    ) -> list[str]:
        codecs = {"mp3": "libmp3lame", "aac": "aac", "wav": "pcm_s16le",
                  "ogg": "libvorbis", "m4a": "aac"}
        cmd = [self._ffmpeg_path, "-y", "-i", input_path, "-vn",
               "-c:a", codecs.get(format, "libmp3lame")]
        if format == "mp3":
            cmd += ["-q:a", "2"]
        elif format in ("aac", "m4a"):
            cmd += ["-b:a", "192k"]
        cmd.append(output_path)
        return cmd

    # ── running + progress ──────────────────────────────────────

    def build_subtitle_embed_command(
        self, video_path: str, subtitle_path: str, output_path: str,
    ) -> list[str]:
        """Build FFmpeg command to soft-embed subtitles as metadata track."""
        ext = os.path.splitext(subtitle_path)[1].lower()
        cmd = [self._ffmpeg_path, "-y", "-i", video_path]
        if ext in (".srt", ".ass", ".ssa", ".vtt"):
            cmd += ["-i", subtitle_path, "-c", "copy"]
            if output_path.endswith(".mp4"):
                cmd += ["-c:s", "mov_text"]
            else:
                cmd += ["-c:s", "copy"]
            cmd += ["-map", "0:v", "-map", "0:a", "-map", "1:s"]
        else:
            escaped = subtitle_path.replace("\\", "/").replace(":", "\\\\:")
            cmd += ["-vf", f"subtitles='{escaped}'", "-c:a", "copy"]
        cmd.append(output_path)
        return cmd

    def _run_simple(self, cmd: list[str], timeout: int = 3600) -> tuple[int, str, str]:
        """Run FFmpeg without progress parsing."""
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout, creationflags=creationflags)
        return result.returncode, result.stdout, result.stderr

    def run(
        self, cmd: list[str], timeout: int = 3600,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        total_duration: float = 0,
        cancel_event=None,  # threading.Event
    ) -> tuple[int, str, str]:
        """Run FFmpeg with optional real-time progress parsing and cancellation.

        Args:
            progress_callback: Called with (percent: float, message: str)
            total_duration: Video duration in seconds for progress calc.
            cancel_event: threading.Event; when set, terminates FFmpeg.
        """
        if not progress_callback:
            return self._run_simple(cmd, timeout)

        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
        )

        import threading
        stderr_lines = []
        done = threading.Event()

        def read_stderr():
            try:
                for line in proc.stderr:
                    stderr_lines.append(line)
            except Exception:
                pass
            done.set()

        reader = threading.Thread(target=read_stderr, daemon=True)
        reader.start()

        time_re = re.compile(r"time=(\d+):(\d+):(\d+)\.(\d+)")
        last_pct = 0

        while proc.poll() is None or not done.is_set():
            # Check cancel
            if cancel_event and cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                reader.join(timeout=2)
                return -1, "", "Cancelled"

            for line in stderr_lines:
                m = time_re.search(line)
                if m:
                    h, mi, s, cs = int(m[1]), int(m[2]), int(m[3]), int(m[4])
                    elapsed = h * 3600 + mi * 60 + s + cs / 100.0
                    if total_duration > 0:
                        pct = min(99.9, (elapsed / total_duration) * 100)
                        if pct > last_pct + 0.5:
                            last_pct = pct
                            progress_callback(pct, f"Processing... {pct:.0f}%")
            stderr_lines.clear()

            try:
                proc.wait(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                pass

        reader.join(timeout=2)
        stdout = proc.stdout.read() if proc.stdout else ""
        stderr_full = ""

        exit_code = proc.returncode
        if exit_code == 0 and progress_callback:
            progress_callback(100.0, "Complete")

        return exit_code, stdout, stderr_full

    def get_video_duration(self, path: str) -> float:
        """Get video duration in seconds using ffprobe."""
        info = self.get_video_info(path)
        try:
            return float(info.get("format", {}).get("duration", 0))
        except (ValueError, TypeError):
            return 0

    def get_video_info(self, path: str) -> dict:
        """Get video metadata using ffprobe."""
        cmd = [self._ffprobe_path, "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", path]
        exit_code, stdout, _ = self._run_simple(cmd, timeout=30)
        if exit_code == 0 and stdout:
            import json
            return json.loads(stdout)
        return {}

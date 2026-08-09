"""Transcoding orchestration using FFmpeg."""
import os
from typing import Optional, Callable
from src.utils.ffmpeg import FFmpegManager


class Transcoder:
    """Handles video post-processing: transcode, audio extract, with progress."""

    def __init__(self, ffmpeg: FFmpegManager):
        self.ffmpeg = ffmpeg

    def transcode(
        self,
        input_path: str,
        output_path: str,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        video_bitrate: str = "",
        crf: int = 23,
        gpu_device: str = "",
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_event=None,
        fps: float = 0,
        premiere_compatible: bool = True,
        source_is_hdr: bool = False,
        color_primaries: str = "",
        color_trc: str = "",
        colorspace: str = "",
    ) -> bool:
        """Transcode video. Returns True on success."""
        ext = os.path.splitext(output_path)[1].lower()
        codec_map = {
            ".mp4": ("libx264", "aac"), ".mkv": ("libx264", "aac"),
            ".avi": ("libx264", "libmp3lame"), ".webm": ("libvpx-vp9", "libopus"),
            ".mov": ("libx264", "aac"),
        }
        if not video_codec:
            video_codec, audio_codec = codec_map.get(ext, ("libx264", "aac"))

        # Get duration for progress
        duration = self.ffmpeg.get_video_duration(input_path)

        cmd = self.ffmpeg.build_transcode_command(
            input_path=input_path, output_path=output_path,
            video_codec=video_codec, audio_codec=audio_codec,
            video_bitrate=video_bitrate, audio_bitrate="320k" if audio_codec == "aac" else "",
            crf=crf,
            gpu_device=gpu_device,
            fps=fps,
            premiere_compatible=premiere_compatible,
            source_is_hdr=source_is_hdr,
            color_primaries=color_primaries,
            color_trc=color_trc,
            colorspace=colorspace,
        )

        exit_code, _, _ = self.ffmpeg.run(
            cmd, progress_callback=progress_callback, total_duration=duration,
            cancel_event=cancel_event,
        )
        return exit_code == 0

    def extract_audio(
        self, input_path: str, output_path: str, format: str = "mp3",
    ) -> bool:
        cmd = self.ffmpeg.build_audio_extract_command(input_path, output_path, format)
        exit_code, _, _ = self.ffmpeg._run_simple(cmd)
        return exit_code == 0

    def get_video_info(self, path: str) -> dict:
        return self.ffmpeg.get_video_info(path)

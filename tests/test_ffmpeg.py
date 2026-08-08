"""Tests for FFmpeg manager."""
import os
import sys
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from src.utils.ffmpeg import FFmpegManager


class TestFFmpegDiscovery:
    def test_default_init(self):
        mgr = FFmpegManager()
        assert isinstance(mgr.ffmpeg_path, str)
        assert isinstance(mgr.ffprobe_path, str)

    def test_app_data_path_is_under_appdata(self):
        mgr = FFmpegManager()
        assert "ProTube" in str(mgr._app_data)
        assert "ffmpeg" in str(mgr._app_data)

    @patch("src.utils.ffmpeg.shutil.which")
    def test_find_system_ffmpeg(self, mock_which):
        mock_which.side_effect = lambda x: {
            "ffmpeg": "C:/tools/ffmpeg.exe",
            "ffprobe": "C:/tools/ffprobe.exe",
        }.get(x)

        mgr = FFmpegManager()
        mgr._available = False
        mgr._discover_ffmpeg()

        assert mgr.available
        assert mgr.ffmpeg_path == "C:/tools/ffmpeg.exe"
        assert mgr.ffprobe_path == "C:/tools/ffprobe.exe"

    @patch("src.utils.ffmpeg.shutil.which")
    def test_not_available_when_none_found(self, mock_which):
        mock_which.return_value = None

        mgr = FFmpegManager()
        mgr._available = False
        mgr._discover_ffmpeg()

        assert not mgr.available


class TestCommandBuilding:
    @patch("src.utils.ffmpeg.os.path.exists")
    def test_build_transcode_command_basic(self, mock_exists):
        mock_exists.return_value = True
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="input.mp4",
            output_path="output.mp4",
            video_codec="libx264",
            crf=23,
        )

        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "-i" in cmd
        assert "input.mp4" in cmd
        assert "output.mp4" in cmd
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-crf" in cmd
        assert "23" in cmd
        assert "-movflags" in cmd
        assert "+faststart" in cmd

    def test_build_transcode_with_bitrate(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mkv",
            video_bitrate="5M",
            audio_bitrate="192k",
        )

        assert "-b:v" in cmd
        assert "5M" in cmd
        assert "-b:a" in cmd
        assert "192k" in cmd

    def test_build_transcode_with_resolution(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mp4",
            resolution="1280:720",
        )

        assert "-vf" in cmd
        assert "scale=1280:720" in cmd

    def test_build_transcode_with_fps(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mp4",
            fps=60,
        )

        assert "-r" in cmd
        assert "60" in cmd

    def test_build_transcode_no_faststart_for_mkv(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mkv",
        )

        assert "+faststart" not in cmd

    def test_build_audio_extract_mp3(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_audio_extract_command(
            input_path="video.mp4",
            output_path="audio.mp3",
            format="mp3",
        )

        assert "-vn" in cmd
        assert "-c:a" in cmd
        assert "libmp3lame" in cmd
        assert "audio.mp3" in cmd

    def test_build_audio_extract_aac(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_audio_extract_command(
            input_path="video.mp4",
            output_path="audio.aac",
            format="aac",
        )

        assert "-vn" in cmd
        assert "aac" in cmd
        assert "-b:a" in cmd
        assert "192k" in cmd

    def test_build_subtitle_embed_srt(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_subtitle_embed_command(
            video_path="video.mp4",
            subtitle_path="subs.srt",
            output_path="out.mp4",
        )

        assert "-i" in cmd
        assert "subs.srt" in cmd
        assert "-c:s" in cmd
        assert "mov_text" in cmd

    def test_build_subtitle_embed_burn(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_subtitle_embed_command(
            video_path="video.mp4",
            subtitle_path="subs.vtt",
            output_path="out.mp4",
        )

        # vtt also gets soft-embedded now
        assert "subs.vtt" in cmd


class TestEnsureFFmpeg:
    @patch("src.utils.ffmpeg.FFmpegManager.download_ffmpeg")
    def test_ensure_when_available(self, mock_download):
        mgr = FFmpegManager()
        mgr._available = True

        result = mgr.ensure_ffmpeg()

        assert result is True
        mock_download.assert_not_called()

    @patch("src.utils.ffmpeg.FFmpegManager.download_ffmpeg")
    def test_ensure_when_not_available(self, mock_download):
        mock_download.return_value = True
        mgr = FFmpegManager()
        mgr._available = False

        result = mgr.ensure_ffmpeg()

        assert result is True
        mock_download.assert_called_once()


class TestRun:
    @patch("src.utils.ffmpeg.subprocess.run")
    def test_run_ffmpeg_command(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        exit_code, stdout, stderr = mgr.run(["ffmpeg", "-version"])

        assert exit_code == 0
        assert stdout == "output"
        mock_run.assert_called_once()

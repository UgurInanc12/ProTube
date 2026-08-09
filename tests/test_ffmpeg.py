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

    def test_nvidia_h264_target_bitrate_uses_quality_policy_without_crf(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mp4",
            video_codec="h264_nvenc",
            audio_codec="aac",
            video_bitrate="20M",
            fps=60,
            gpu_device="nvidia",
            premiere_compatible=True,
        )

        assert cmd[cmd.index("-preset") + 1] == "p7"
        assert cmd[cmd.index("-tune") + 1] == "hq"
        assert cmd[cmd.index("-rc") + 1] == "vbr"
        assert cmd[cmd.index("-b:v") + 1] == "20M"
        assert cmd[cmd.index("-maxrate") + 1] == "30M"
        assert cmd[cmd.index("-bufsize") + 1] == "40M"
        assert cmd[cmd.index("-multipass") + 1] == "fullres"
        assert cmd[cmd.index("-rc-lookahead") + 1] == "32"
        assert "-spatial-aq" in cmd and "-temporal-aq" in cmd
        assert "-crf" not in cmd
        assert cmd[cmd.index("-profile:v") + 1] == "high"
        assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
        assert cmd[cmd.index("-b:a") + 1] == "320k"
        assert cmd[cmd.index("-ar") + 1] == "48000"
        assert cmd[cmd.index("-ac") + 1] == "2"

    def test_nvidia_hevc_uses_uhq_tune(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mp4",
            video_codec="hevc_nvenc",
            video_bitrate="20M",
            gpu_device="nvidia",
        )

        assert cmd[cmd.index("-tune") + 1] == "uhq"
        assert "-cq" not in cmd
        assert cmd[cmd.index("-b:v") + 1] == "20M"

    def test_amd_hevc_target_bitrate_uses_amf_quality_options(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mp4",
            video_codec="hevc_amf",
            video_bitrate="20M",
            gpu_device="amd",
            premiere_compatible=True,
        )

        assert cmd[cmd.index("-usage") + 1] == "high_quality"
        assert cmd[cmd.index("-quality") + 1] == "high_quality"
        assert cmd[cmd.index("-rc") + 1] == "vbr_peak"
        assert cmd[cmd.index("-b:v") + 1] == "20M"
        assert cmd[cmd.index("-maxrate") + 1] == "30M"
        assert cmd[cmd.index("-bufsize") + 1] == "40M"
        assert "-preanalysis" in cmd
        assert "-vbaq" in cmd
        assert "-crf" not in cmd
        assert cmd[cmd.index("-tag:v") + 1] == "hvc1"

    def test_intel_qsv_target_bitrate_uses_veryslow_and_extended_brc(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mp4",
            video_codec="h264_qsv",
            video_bitrate="20M",
            gpu_device="intel",
            premiere_compatible=True,
        )

        assert cmd[cmd.index("-preset") + 1] == "veryslow"
        assert cmd[cmd.index("-b:v") + 1] == "20M"
        assert cmd[cmd.index("-maxrate") + 1] == "30M"
        assert cmd[cmd.index("-bufsize") + 1] == "40M"
        assert cmd[cmd.index("-extbrc") + 1] == "1"
        assert cmd[cmd.index("-look_ahead") + 1] == "1"
        assert cmd[cmd.index("-look_ahead_depth") + 1] == "40"
        assert "-crf" not in cmd

    def test_intel_qsv_hevc_uses_depth_without_h264_only_look_ahead_switch(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mp4",
            video_codec="hevc_qsv",
            video_bitrate="20M",
            gpu_device="intel",
        )

        assert "-look_ahead" not in cmd
        assert cmd[cmd.index("-look_ahead_depth") + 1] == "40"

    def test_premiere_flags_are_not_forced_on_non_mp4_outputs(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mkv",
            video_codec="hevc_nvenc",
            video_bitrate="20M",
            gpu_device="nvidia",
            fps=30,
            premiere_compatible=False,
        )

        assert "-tag:v" not in cmd
        assert "-fps_mode" not in cmd
        assert "-movflags" not in cmd

    def test_premiere_profile_flags_apply_to_mov_output(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mov",
            video_codec="h264_nvenc",
            video_bitrate="20M",
            gpu_device="nvidia",
            fps=30,
            premiere_compatible=True,
        )

        assert cmd[cmd.index("-profile:v") + 1] == "high"
        assert cmd[cmd.index("-fps_mode") + 1] == "cfr"

    def test_premiere_hevc_hdr_uses_main10_and_preserves_color_metadata(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mp4",
            video_codec="hevc_nvenc",
            video_bitrate="15M",
            gpu_device="nvidia",
            fps=30,
            premiere_compatible=True,
            source_is_hdr=True,
            color_primaries="bt2020",
            color_trc="smpte2084",
            colorspace="bt2020nc",
        )

        assert cmd[cmd.index("-profile:v") + 1] == "main10"
        assert cmd[cmd.index("-pix_fmt") + 1] == "p010le"
        assert cmd[cmd.index("-tag:v") + 1] == "hvc1"
        assert cmd[cmd.index("-color_primaries") + 1] == "bt2020"
        assert cmd[cmd.index("-color_trc") + 1] == "smpte2084"
        assert cmd[cmd.index("-colorspace") + 1] == "bt2020nc"
        assert cmd[cmd.index("-fps_mode") + 1] == "cfr"
        assert cmd[cmd.index("-g") + 1] == "60"
        assert cmd[cmd.index("-keyint_min") + 1] == "60"

    def test_software_target_bitrate_does_not_mix_crf_with_vbv(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mp4",
            video_codec="libx264",
            video_bitrate="5M",
            crf=23,
        )

        assert "-b:v" in cmd
        assert "-maxrate" in cmd
        assert "-bufsize" in cmd
        assert "-crf" not in cmd

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

    def test_premiere_cfr_preserves_fractional_frame_rate(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mp4",
            video_codec="h264_nvenc",
            video_bitrate="20M",
            gpu_device="nvidia",
            fps=29.97,
            premiere_compatible=True,
        )

        assert cmd[cmd.index("-r") + 1] == "29.97"
        assert cmd[cmd.index("-g") + 1] == "60"

    def test_build_transcode_no_faststart_for_mkv(self):
        mgr = FFmpegManager()
        mgr._ffmpeg_path = "ffmpeg"

        cmd = mgr.build_transcode_command(
            input_path="in.mp4",
            output_path="out.mkv",
        )

        assert "+faststart" not in cmd

    def test_bitrate_scaling_preserves_units(self):
        assert FFmpegManager._scale_bitrate("20M", 1.5) == "30M"
        assert FFmpegManager._scale_bitrate("2500k", 2.0) == "5000K"
        assert FFmpegManager._scale_bitrate("8000000", 1.5) == "12000000"

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

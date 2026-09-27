import pytest

import gallery
from conftest import requires_ffmpeg


@requires_ffmpeg
def test_probe_video_plain_mp4(media_dir):
    info = gallery.probe_video(media_dir / "plain.mp4")
    assert info is not None
    assert info["index"] == 0
    assert info["duration"] == pytest.approx(2.0, abs=0.2)
    assert info["meta"]["format"] == "320x240"
    assert info["meta"]["video_codec"] == "h264"
    assert info["meta"]["audio_codec"] == "aac"
    assert info["meta"]["bitrate"].endswith("kb/s")
    assert info["meta"]["filename"] == "plain.mp4"


@requires_ffmpeg
def test_probe_video_mkv_container(media_dir):
    info = gallery.probe_video(media_dir / "plain.mkv")
    assert info is not None
    assert info["meta"]["format"] == "320x240"
    assert info["meta"]["video_codec"] == "h264"


@requires_ffmpeg
def test_probe_video_ignores_attached_pic_cover_art(media_dir):
    # ffprobe reports the cover image as a "video" stream; probe_video must
    # recognise stream_disposition=attached_pic and treat this as "no video".
    assert gallery.probe_video(media_dir / "audio_with_cover.m4a") is None


@requires_ffmpeg
def test_probe_video_audio_only_no_video_stream(media_dir):
    assert gallery.probe_video(media_dir / "audio_only.mp3") is None


@requires_ffmpeg
def test_probe_video_corrupt_file_returns_none(media_dir):
    assert gallery.probe_video(media_dir / "corrupt.mp4") is None


@requires_ffmpeg
def test_probe_video_missing_file_returns_none(media_dir):
    assert gallery.probe_video(media_dir / "does_not_exist.mp4") is None

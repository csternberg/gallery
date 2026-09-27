import pytest

import gallery
from conftest import requires_ffmpeg


@requires_ffmpeg
def test_extract_thumbnails_plain_mp4(media_dir, tmp_path):
    info = gallery.probe_video(media_dir / "plain.mp4")
    files, errors = gallery.extract_thumbnails(
        media_dir / "plain.mp4", info["index"], info["duration"], 4, tmp_path, jobs=2)
    assert errors == []
    assert len(files) == 4
    assert files == sorted(files)  # timeline order
    for f in files:
        assert f.stat().st_size > 0


@requires_ffmpeg
def test_extract_thumbnails_mkv_container(media_dir, tmp_path):
    info = gallery.probe_video(media_dir / "plain.mkv")
    files, errors = gallery.extract_thumbnails(
        media_dir / "plain.mkv", info["index"], info["duration"], 3, tmp_path, jobs=1)
    assert errors == []
    assert len(files) == 3


@requires_ffmpeg
def test_extract_thumbnails_more_than_a_few_closely_spaced(media_dir, tmp_path):
    info = gallery.probe_video(media_dir / "plain.mp4")
    files, errors = gallery.extract_thumbnails(
        media_dir / "plain.mp4", info["index"], info["duration"], 8, tmp_path, jobs=4)
    assert errors == []
    assert len(files) == 8


@requires_ffmpeg
def test_extract_thumbnails_reports_seek_past_end_as_error_not_crash(media_dir, tmp_path):
    # With N thumbnails spread over [0, duration), the last timestamp approaches the
    # very end of the clip; on a short 2s/10fps source it can land past the last
    # decodable frame. gallery documents this as a non-fatal per-frame error - make
    # sure that stays true instead of raising or silently losing files.
    info = gallery.probe_video(media_dir / "plain.mp4")
    files, errors = gallery.extract_thumbnails(
        media_dir / "plain.mp4", info["index"], info["duration"], 20, tmp_path, jobs=4)
    assert len(files) + len(errors) == 20
    for err in errors:
        assert "frame" in err


@requires_ffmpeg
def test_extract_thumbnails_single_frame(media_dir, tmp_path):
    info = gallery.probe_video(media_dir / "plain.mp4")
    files, errors = gallery.extract_thumbnails(
        media_dir / "plain.mp4", info["index"], info["duration"], 1, tmp_path, jobs=1)
    assert errors == []
    assert len(files) == 1


@pytest.mark.skip(reason=(
    "Could not reproduce ffmpeg's container-level rotation signalling "
    "(mov display-matrix / H.264 display-orientation SEI) deterministically via the "
    "ffmpeg 7.1.1-full_build CLI: neither '-metadata:s:v:0 rotate=90' (plain re-encode "
    "or -c copy remux) nor '-bsf:v h264_metadata=rotate=90' produced a side_data_list "
    "ffprobe could see, so extracted frames stayed at the coded (unrotated) size. "
    "Verify manually with a real phone-shot clip instead: extracted frame dimensions "
    "should come out portrait (swapped w/h) relative to the stream's coded width/height."
))
def test_extract_thumbnails_autorotates_phone_video():
    pass

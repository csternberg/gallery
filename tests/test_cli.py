import os
import subprocess
import sys

import pytest
from PIL import Image

import gallery
from conftest import GALLERY_SCRIPT, copy_fixture, requires_ffmpeg, run_gallery


@requires_ffmpeg
def test_basic_run_creates_gallery_and_thumbs(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir)
    result = run_gallery(["-F", "-M", "-N", "4", "-j", "2", "plain.mp4"], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (workdir / "plain_gallery.jpg").exists()
    thumbs_dir = workdir / "plain_thumbs"
    assert thumbs_dir.is_dir()
    assert len(list(thumbs_dir.glob("*.jpg"))) == 4


@requires_ffmpeg
def test_rerun_never_overwrites_gets_suffixed(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir)
    r1 = run_gallery(["-N", "2", "plain.mp4"], cwd=workdir)
    r2 = run_gallery(["-N", "2", "plain.mp4"], cwd=workdir)
    assert r1.returncode == 0 and r2.returncode == 0
    assert (workdir / "plain_gallery.jpg").exists()
    assert (workdir / "plain_gallery_01.jpg").exists()


@requires_ffmpeg
def test_corrupt_file_is_skipped_not_a_failure(media_dir, workdir):
    copy_fixture(media_dir, "corrupt.mp4", workdir)
    result = run_gallery(["corrupt.mp4"], cwd=workdir)
    assert result.returncode == 0
    assert "[SKIP]" in result.stdout
    assert not (workdir / "corrupt_gallery.jpg").exists()


@requires_ffmpeg
def test_attached_pic_audio_file_is_skipped_not_a_failure(media_dir, workdir):
    copy_fixture(media_dir, "audio_with_cover.m4a", workdir)
    result = run_gallery(["audio_with_cover.m4a"], cwd=workdir)
    assert result.returncode == 0
    assert "[SKIP]" in result.stdout


@requires_ffmpeg
def test_one_bad_file_does_not_fail_the_whole_batch(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir)
    copy_fixture(media_dir, "corrupt.mp4", workdir)
    result = run_gallery(["-N", "2", "-C"], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (workdir / "plain_gallery.jpg").exists()


@requires_ffmpeg
def test_filename_with_brackets(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir, dest_name="clip[1].mp4")
    result = run_gallery(["-N", "2", "clip[1].mp4"], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (workdir / "clip[1]_gallery.jpg").exists()


@requires_ffmpeg
def test_recursive_finds_nested_videos(media_dir, workdir):
    nested = workdir / "sub" / "deeper"
    nested.mkdir(parents=True)
    copy_fixture(media_dir, "plain.mp4", nested)
    result = run_gallery(["-R", "-N", "2"], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (nested / "plain_gallery.jpg").exists()


@requires_ffmpeg
def test_no_matching_files_exits_nonzero(workdir):
    result = run_gallery(["-C"], cwd=workdir)
    assert result.returncode == 1
    assert "[ERROR]" in result.stdout


@requires_ffmpeg
def test_missing_ffmpeg_on_path_errors_cleanly_and_exits(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir)
    env = os.environ.copy()
    env["PATH"] = ""
    result = subprocess.run(
        [sys.executable, str(GALLERY_SCRIPT), "plain.mp4"],
        cwd=workdir, capture_output=True, text=True, env=env,
    )
    assert result.returncode == 1
    assert "ffmpeg" in result.stdout


@requires_ffmpeg
def test_redirected_output_has_no_ansi_escapes(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir)
    result = run_gallery(["-N", "2", "plain.mp4"], cwd=workdir)
    assert "\x1b[" not in result.stdout
    assert "[OK]" in result.stdout


@requires_ffmpeg
def test_x_and_y_flags_control_final_gallery_size(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir)
    result = run_gallery(["-N", "4", "-X", "200", "-Y", "100", "plain.mp4"], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr
    with Image.open(workdir / "plain_gallery.jpg") as img:
        assert img.size == (200, 100)


@requires_ffmpeg
def test_scale_flag_requires_metadata_flag(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir)
    result = run_gallery(["-N", "2", "-S", "plain.mp4"], cwd=workdir)
    assert result.returncode != 0
    assert "-S" in (result.stdout + result.stderr)
    assert "-M" in (result.stdout + result.stderr)


@requires_ffmpeg
def test_scale_flag_grows_metadata_header_on_wide_gallery(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir, dest_name="unscaled.mp4")
    copy_fixture(media_dir, "plain.mp4", workdir, dest_name="scaled.mp4")
    r1 = run_gallery(["-N", "4", "-M", "-X", "1600", "unscaled.mp4"], cwd=workdir)
    r2 = run_gallery(["-N", "4", "-M", "-S", "-X", "1600", "scaled.mp4"], cwd=workdir)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    assert r2.returncode == 0, r2.stdout + r2.stderr
    with Image.open(workdir / "unscaled_gallery.jpg") as a, Image.open(workdir / "scaled_gallery.jpg") as b:
        assert a.size[0] == b.size[0] == 1600
        assert b.size[1] > a.size[1]


@requires_ffmpeg
@pytest.mark.parametrize("flag", ["-s", "-S"])
def test_scale_flag_is_case_insensitive(media_dir, workdir, flag):
    copy_fixture(media_dir, "plain.mp4", workdir)
    result = run_gallery(["-N", "2", "-M", flag, "plain.mp4"], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr


def test_rejects_non_positive_thumbnail_count(workdir):
    result = subprocess.run(
        [sys.executable, str(GALLERY_SCRIPT), "-N", "0", "-C"],
        cwd=workdir, capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_no_source_selection_errors(workdir):
    result = subprocess.run(
        [sys.executable, str(GALLERY_SCRIPT)],
        cwd=workdir, capture_output=True, text=True,
    )
    assert result.returncode != 0


@pytest.mark.parametrize("flag", ["-V", "-v", "--version"])
def test_version_flag_upper_and_lower(workdir, flag):
    result = subprocess.run(
        [sys.executable, str(GALLERY_SCRIPT), flag],
        cwd=workdir, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert gallery.VERSION in (result.stdout + result.stderr)


@pytest.mark.parametrize("flag", ["-h", "-H", "--help"])
def test_help_flag_upper_and_lower(workdir, flag):
    result = subprocess.run(
        [sys.executable, str(GALLERY_SCRIPT), flag],
        cwd=workdir, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


@requires_ffmpeg
@pytest.mark.parametrize("case", ["upper", "lower"])
def test_switches_are_case_insensitive(media_dir, workdir, case):
    copy_fixture(media_dir, "plain.mp4", workdir)
    out_dir = workdir / "out"
    n_flag, o_flag, j_flag = ("-N", "-O", "-J") if case == "upper" else ("-n", "-o", "-j")
    result = run_gallery([n_flag, "2", j_flag, "2", o_flag, str(out_dir), "plain.mp4"], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out_dir / "plain_gallery.jpg").exists()


@requires_ffmpeg
def test_output_flag_places_gallery_and_thumbs_away_from_source(media_dir, workdir):
    nested = workdir / "videos"
    nested.mkdir()
    copy_fixture(media_dir, "plain.mp4", nested)
    out_dir = workdir / "results"
    result = run_gallery(["-N", "2", "-F", "-O", str(out_dir), str(nested / "plain.mp4")], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out_dir / "plain_gallery.jpg").exists()
    assert (out_dir / "plain_thumbs").is_dir()
    assert not (nested / "plain_gallery.jpg").exists()
    assert not (nested / "plain_thumbs").exists()


@requires_ffmpeg
def test_log_flag_writes_full_run_log(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir)
    result = run_gallery(["-N", "2", "-L", "plain.mp4"], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr
    log_path = workdir / "gallery.log"
    assert log_path.exists()
    content = log_path.read_text()
    assert "plain.mp4" in content
    assert "Saved gallery" in content


@requires_ffmpeg
def test_no_log_flag_writes_no_log_file_when_no_errors(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir)
    result = run_gallery(["-N", "2", "plain.mp4"], cwd=workdir)
    assert result.returncode == 0
    assert not (workdir / "gallery.log").exists()
    assert not (workdir / "gallery_errors.log").exists()


@requires_ffmpeg
def test_error_log_is_always_written_when_problems_occur(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir)
    # An impossible frame count relative to a 2s test clip pushes at least one
    # seek past the last decodable frame, producing a genuine per-frame error.
    result = run_gallery(["-N", "60", "plain.mp4"], cwd=workdir)
    error_log = workdir / "gallery_errors.log"
    if result.returncode != 0:
        assert error_log.exists()
        assert "[ERROR]" in error_log.read_text() or "[WARN]" in error_log.read_text()
        assert not (workdir / "gallery.log").exists()  # -L wasn't passed
    else:
        # Even 60 evenly spaced frames over 2s might all land cleanly on this
        # ffmpeg build; nothing to assert beyond "no crash".
        assert not error_log.exists()


@requires_ffmpeg
def test_log_stays_in_invocation_folder_even_with_output_flag(media_dir, workdir):
    nested = workdir / "videos"
    nested.mkdir()
    copy_fixture(media_dir, "plain.mp4", nested)
    out_dir = workdir / "results"
    result = run_gallery(["-N", "2", "-L", "-O", str(out_dir), str(nested / "plain.mp4")], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (workdir / "gallery.log").exists()
    assert not (out_dir / "gallery.log").exists()


@requires_ffmpeg
def test_exactly_one_log_and_one_error_log_per_run(media_dir, workdir):
    copy_fixture(media_dir, "plain.mp4", workdir, dest_name="a.mp4")
    copy_fixture(media_dir, "plain.mp4", workdir, dest_name="b.mp4")
    copy_fixture(media_dir, "corrupt.mp4", workdir, dest_name="c.mp4")
    result = run_gallery(["-N", "2", "-L", "-C"], cwd=workdir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(list(workdir.glob("gallery*.log"))) == 1
    # A skipped non-video file is not an error, so no error log should appear here.
    assert not (workdir / "gallery_errors.log").exists()


def test_dot_log_files_are_not_picked_up_as_videos(workdir):
    (workdir / "notes.log").write_bytes(b"not a video")
    result = subprocess.run(
        [sys.executable, str(GALLERY_SCRIPT), "-C"],
        cwd=workdir, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "No valid video files found" in result.stdout

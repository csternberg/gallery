import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

GALLERY_SCRIPT = REPO_ROOT / "gallery.py"

FFMPEG_MISSING = shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None
requires_ffmpeg = pytest.mark.skipif(FFMPEG_MISSING, reason="ffmpeg/ffprobe not on PATH")


def _run_ffmpeg(*args):
    result = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"ffmpeg failed: {result.stderr}\nargs={args}"


@pytest.fixture(scope="session")
def media_dir(tmp_path_factory):
    """Build the small set of synthetic media fixtures used across the suite, once per run."""
    if FFMPEG_MISSING:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    d = tmp_path_factory.mktemp("media")

    # Ordinary 2s video with audio, landscape - the common case.
    _run_ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=2",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                str(d / "plain.mp4"))

    # Same content, mkv container.
    _run_ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=2",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                str(d / "plain.mkv"))

    # Attached cover art on an audio file: ffprobe reports a "video" stream that
    # probe_video() must recognise (via disposition.attached_pic) and ignore.
    _run_ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=64x64", "-frames:v", "1",
                str(d / "cover.png"))
    _run_ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-i", str(d / "cover.png"),
                "-map", "0:a", "-map", "1:v",
                "-c:a", "aac", "-c:v", "mjpeg", "-disposition:v:0", "attached_pic",
                str(d / "audio_with_cover.m4a"))

    # Audio-only, no video/cover stream at all.
    _run_ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-c:a", "libmp3lame", str(d / "audio_only.mp3"))

    # Corrupt / truncated file with a video extension - ffprobe must fail on it cleanly.
    (d / "corrupt.mp4").write_bytes(bytes(range(200)))

    return d


@pytest.fixture()
def workdir(tmp_path, monkeypatch):
    """A scratch cwd for CLI tests, isolated from other tests' output files."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def copy_fixture(media_dir, name, dest_dir, dest_name=None):
    dest = Path(dest_dir) / (dest_name or name)
    shutil.copy(media_dir / name, dest)
    return dest


def run_gallery(args, cwd, env=None):
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(GALLERY_SCRIPT), *args],
        cwd=cwd, capture_output=True, text=True, env=full_env,
    )

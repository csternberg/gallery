#!/usr/bin/env python3
import os
import sys
import glob
import json
import math
import shutil
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[ERROR] Pillow library not found. Install with: pip install pillow")
    sys.exit(1)


VERSION = "1.1.0"


# ------------------------------------------------------------
# Progress / logging
# ------------------------------------------------------------
class Progress:
    """Per-file progress line. Redraws in place on a terminal, prints one line per file otherwise."""

    def __init__(self, stream=sys.stdout):
        self.stream = stream
        self.live = stream.isatty()
        self.prefix = ""
        self.visible = False
        self.lines = []  # full transcript, for -L / the always-on error log

    def start(self, index: int, total: int, name: str):
        self.prefix = f"[{index}/{total}] {name}"
        line = f"[INFO] {self.prefix}"
        self.lines.append(line)
        if self.live:
            self._draw("starting")
        else:
            print(line, file=self.stream, flush=True)

    def update(self, done: int, total: int, label: str = "thumbnails"):
        if not self.live:
            return
        width = 20
        filled = width * done // total if total else width
        self._draw(f"[{'#' * filled}{'-' * (width - filled)}] {done}/{total} {label}")

    def phase(self, label: str):
        if self.live:
            self._draw(label)

    def log(self, message: str):
        """Print a message without leaving a half-drawn progress line behind."""
        self.lines.append(message)
        self.clear()
        print(message, file=self.stream, flush=True)

    def clear(self):
        if self.live and self.visible:
            self.stream.write("\r\x1b[K")
            self.stream.flush()
            self.visible = False

    def _draw(self, tail: str):
        cols = shutil.get_terminal_size((80, 24)).columns
        index, _, name = self.prefix.partition(" ")
        room = cols - 1 - len(index) - len(tail) - 3  # separators; keep the bar, trim the name
        if len(name) > room:
            name = "..." + name[len(name) - (room - 3):] if room > 3 else ""
        self.stream.write(f"\r\x1b[K{index} {name}  {tail}")
        self.stream.flush()
        self.visible = True


# ------------------------------------------------------------
# Prerequisites check
# ------------------------------------------------------------
def check_prerequisites():
    for cmd in ("ffmpeg", "ffprobe"):
        if shutil.which(cmd) is None:
            print(f"[ERROR] Required command '{cmd}' not found. Install ffmpeg.")
            sys.exit(1)


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------
def safe_name(base: Path) -> Path:
    """Return a unique path by appending _01, _02, etc if needed."""
    if not base.exists():
        return base
    stem, suffix = base.stem, base.suffix
    i = 1
    while True:
        candidate = base.with_name(f"{stem}_{i:02d}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1


# Extensions to skip immediately (obvious non-video)
SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff",
    ".txt", ".md", ".rtf", ".doc", ".docx", ".pdf", ".log", ".lst",
    ".csv", ".json", ".xml", ".yaml", ".yml",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".mp3", ".wav", ".flac", ".aac", ".ogg",
    ".exe", ".dll", ".so",
}

def is_potential_video(path: Path) -> bool:
    """Quick skip for obvious non-video files"""
    return path.suffix.lower() not in SKIP_EXTENSIONS


def format_duration(seconds) -> str:
    if seconds is None:
        return "Unknown"
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _to_float(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f > 0 else None


def probe_video(path: Path):
    """
    Inspect a file with a single ffprobe call.
    Returns None if the file has no real video stream (or ffprobe fails),
    otherwise a dict with the stream index, duration (seconds) and display metadata.
    """
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-of", "json",
             "-show_entries",
             "format=duration,bit_rate:"
             "stream=index,codec_type,codec_name,width,height,duration:stream_disposition=attached_pic",
             str(path)],
            capture_output=True, text=True, errors="replace"
        )
        if res.returncode != 0:
            return None
        data = json.loads(res.stdout or "{}")
    except (OSError, ValueError):
        return None

    streams = data.get("streams", [])
    # Cover art in audio files shows up as a "video" stream; ignore it.
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        return None
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})

    duration = _to_float(fmt.get("duration")) or _to_float(video.get("duration"))
    bitrate = fmt.get("bit_rate", "")

    return {
        "index": video["index"],
        "duration": duration,
        "meta": {
            "filename": path.name,
            "duration": format_duration(duration),
            "format": f"{video.get('width') or '?'}x{video.get('height') or '?'}",
            "video_codec": video.get("codec_name") or "Unknown",
            "audio_codec": (audio or {}).get("codec_name") or "Unknown",
            "bitrate": f"{int(bitrate) // 1000} kb/s" if str(bitrate).isdigit() else "Unknown",
        },
    }


# ------------------------------------------------------------
# Thumbnail extraction
# ------------------------------------------------------------
def _extract_one(video_path: Path, stream_index: int, ts: float, thumb_file: Path):
    """Extract a single frame. Returns an error string, or None on success."""
    res = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
         "-ss", f"{ts:.3f}", "-i", str(video_path),
         "-map", f"0:{stream_index}", "-frames:v", "1", "-an", "-sn", "-dn",
         "-q:v", "2", str(thumb_file)],
        capture_output=True, text=True, errors="replace"
    )
    if res.returncode != 0:
        return res.stderr.strip() or f"ffmpeg exited with {res.returncode}"
    # ffmpeg exits 0 without writing anything if the seek lands past the last frame
    if not thumb_file.exists() or thumb_file.stat().st_size == 0:
        return "no frame produced"
    return None


def extract_thumbnails(video_path: Path, stream_index: int, duration: float, count: int,
                       out_dir: Path, jobs: int, progress: Progress = None):
    """
    Extract `count` evenly spaced frames in parallel.
    Returns (list of successfully written files in timeline order, list of error strings).
    """
    timestamps = [duration * i / (count + 1) for i in range(1, count + 1)]
    files = [out_dir / f"thumb_{i:03d}.jpg" for i in range(1, count + 1)]
    errors = []
    done = 0

    if progress:
        progress.update(0, count)
    with ThreadPoolExecutor(max_workers=max(1, min(jobs, count))) as pool:
        futures = {pool.submit(_extract_one, video_path, stream_index, ts, f): i
                   for i, (ts, f) in enumerate(zip(timestamps, files), start=1)}
        for fut in as_completed(futures):
            err = fut.result()
            if err:
                errors.append(f"frame {futures[fut]}: {err}")
            done += 1
            if progress:
                progress.update(done, count)

    return [f for f in files if f.exists() and f.stat().st_size > 0], errors


# ------------------------------------------------------------
# Gallery creation
# ------------------------------------------------------------
FONT_CANDIDATES = [
    "arial.ttf", "Arial.ttf", "DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

def load_font(size: int):
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1, scalable
    except TypeError:
        return ImageFont.load_default()


METADATA_FONT_SIZE, METADATA_LINE_HEIGHT, METADATA_PAD = 16, 22, 10


def metadata_layout(total_x: int, scale: bool = False):
    """Font size/line height/padding for the -M metadata bar.

    Fixed at 16px/22px/10px unless `scale` (-S) is set, in which case they grow
    with the gallery's width so text that was legible at ~300px doesn't shrink
    to unreadable on a 1000px+ wide gallery. The fixed values are the floor.
    """
    if not scale:
        return METADATA_FONT_SIZE, METADATA_LINE_HEIGHT, METADATA_PAD
    font_size = max(METADATA_FONT_SIZE, round(total_x / 55))
    line_h = round(font_size * 1.4)
    pad = round(font_size * 0.6)
    return font_size, line_h, pad


def make_gallery(thumbs: list, out_file: Path, total_x: int = None, total_y: int = None,
                 metadata: dict = None, thumbs_dir: Path = None, scale_text: bool = False):
    """
    Combine thumbnails into a single gallery image (optional metadata bar).
    If `thumbs_dir` is given, the resized individual thumbnails are saved there.
    Returns the path written, or None on failure.
    """
    images = []
    try:
        for t in thumbs:
            try:
                images.append(Image.open(t))
            except OSError:
                continue
        if not images:
            print(f"[ERROR] Could not open any thumbnail images for {out_file}")
            return None

        # Layout is based on the frames we actually have, not the number requested
        count = len(images)
        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)

        w, h = images[0].size
        aspect_ratio = (w * cols) / (h * rows)
        if total_x and not total_y:
            total_y = int(total_x / aspect_ratio)
        elif total_y and not total_x:
            total_x = int(total_y * aspect_ratio)
        elif not total_x and not total_y:
            total_x, total_y = w * cols, h * rows

        cell_w, cell_h = max(1, total_x // cols), max(1, total_y // rows)

        # Metadata bar
        text_lines, font, line_h, pad, meta_height = [], None, 0, 10, 0
        if metadata:
            font_size, line_h, pad = metadata_layout(total_x, scale=scale_text)
            font = load_font(font_size)
            text_lines = [
                f"Filename: {metadata['filename']}",
                f"Duration: {metadata['duration']}",
                f"Format: {metadata['format']}",
                f"Video Codec: {metadata['video_codec']}",
                f"Audio Codec: {metadata['audio_codec']}",
                f"Bitrate: {metadata['bitrate']}",
            ]
            meta_height = 2 * pad + line_h * len(text_lines)

        gallery = Image.new("RGB", (total_x, total_y + meta_height), (0, 0, 0))
        if text_lines:
            draw = ImageDraw.Draw(gallery)
            for n, line in enumerate(text_lines):
                draw.text((pad, pad + n * line_h), line, fill="white", font=font)

        if thumbs_dir:
            thumbs_dir.mkdir(parents=True, exist_ok=True)

        for idx, img in enumerate(images):
            # JPEG draft mode lets the decoder downscale by 1/2, 1/4, 1/8 while reading,
            # which is much faster when the cells are smaller than the source frames.
            img.draft("RGB", (cell_w, cell_h))
            resized = img.convert("RGB").resize((cell_w, cell_h), Image.LANCZOS)
            r, c = divmod(idx, cols)
            gallery.paste(resized, (c * cell_w, r * cell_h + meta_height))
            if thumbs_dir:
                resized.save(thumbs_dir / f"thumb_{idx + 1:03d}.jpg", quality=95)
    finally:
        for img in images:
            img.close()

    out_file = safe_name(out_file)
    gallery.save(out_file, quality=92)
    return out_file


# ------------------------------------------------------------
# File discovery
# ------------------------------------------------------------
def find_videos(patterns, recursive=False):
    seen, videos = set(), []
    for pat in patterns:
        # A literal path always wins: glob would treat "clip[1].mp4" as a character class
        matched = [pat] if os.path.isfile(pat) else glob.glob(pat, recursive=recursive)
        for f in sorted(matched):
            p = Path(f)
            if not p.is_file() or not is_potential_video(p):
                continue
            key = p.resolve()
            if key not in seen:
                seen.add(key)
                videos.append(p)
    return videos


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def positive_int(value):
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return n


def main():
    parser = argparse.ArgumentParser(
        description="Create thumbnail galleries from video files using ffmpeg.",
        add_help=False,
    )

    parser.add_argument("-h", "-H", "--help", action="help", help="Show this help message and exit")
    parser.add_argument("-V", "-v", "--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("filenames", nargs="*", help="Video filename(s) or wildcard pattern(s)")
    parser.add_argument("-C", "-c", action="store_true", help="Process all video files in current folder")
    parser.add_argument("-R", "-r", action="store_true",
                        help="Recurse into subfolders (all of them when no filenames are given)")
    parser.add_argument("-N", "-n", type=positive_int, default=16, help="Number of thumbnails to include (default: 16)")
    parser.add_argument("-X", "-x", type=positive_int, help="Total horizontal pixels (optional)")
    parser.add_argument("-Y", "-y", type=positive_int, help="Total vertical pixels (optional)")
    parser.add_argument("-F", "-f", action="store_true", help="Also save individual thumbnails in a folder")
    parser.add_argument("-M", "-m", action="store_true", help="Add metadata bar above gallery")
    parser.add_argument("-S", "-s", action="store_true",
                        help="Scale the -M metadata text size with gallery width, so it stays readable "
                             "on wide galleries (requires -M; no effect without it)")
    parser.add_argument("-O", "-o", "--output", metavar="DIR",
                        help="Save galleries and thumbnails in DIR instead of next to each source file")
    parser.add_argument("-L", "-l", action="store_true",
                        help="Write one full run log (gallery.log) in the folder gallery.py was run from. "
                             "One error log (gallery_errors.log) is always written there too if any "
                             "problems occur")
    parser.add_argument("-j", "-J", "--jobs", type=positive_int, default=min(8, os.cpu_count() or 4),
                        help="Parallel ffmpeg processes per video (default: %(default)s)")

    args = parser.parse_args()
    if args.S and not args.M:
        parser.error("-S/-s requires -M/-m")
    check_prerequisites()

    out_dir = Path(args.output) if args.output else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    cwd = glob.escape(str(Path.cwd()))
    if args.filenames:
        files = find_videos(args.filenames, recursive=args.R)
    elif args.R:
        files = find_videos([os.path.join(cwd, "**", "*")], recursive=True)
    elif args.C:
        files = find_videos([os.path.join(cwd, "*")])
    else:
        parser.error("No input files specified. Use -C, -R, or provide filenames.")

    if not files:
        print("[ERROR] No valid video files found.")
        sys.exit(1)

    progress = Progress()
    failed = 0

    for n, video in enumerate(files, start=1):
        try:
            progress.start(n, len(files), video.name)

            info = probe_video(video)
            if info is None:
                progress.log(f"[SKIP] Not a video file: {video}")
                continue
            if info["duration"] is None:
                progress.log(f"[ERROR] Could not get duration for {video}")
                failed += 1
                continue

            with TemporaryDirectory() as tmpdir:
                thumbs, errors = extract_thumbnails(
                    video, info["index"], info["duration"], args.N, Path(tmpdir), args.jobs, progress
                )
                for err in errors:
                    progress.log(f"[ERROR] {video.name}: {err}")

                if not thumbs:
                    progress.log(f"[WARN] No thumbnails to make gallery for {video}")
                    failed += 1
                    continue

                progress.phase("building gallery")
                target_dir = out_dir or video.parent
                thumbs_dir = safe_name(target_dir / f"{video.stem}_thumbs") if args.F else None
                out = make_gallery(
                    thumbs,
                    target_dir / f"{video.stem}_gallery.jpg",
                    total_x=args.X,
                    total_y=args.Y,
                    metadata=info["meta"] if args.M else None,
                    thumbs_dir=thumbs_dir,
                    scale_text=args.S,
                )

            if out is None:
                failed += 1
                continue
            progress.log(f"[OK] [{n}/{len(files)}] Saved gallery: {out}")
            if thumbs_dir:
                progress.log(f"[OK] Saved individual thumbnails in: {thumbs_dir}")
            if errors:
                failed += 1

        except Exception as e:
            progress.log(f"[ERROR] Unexpected error with {video}: {e}")
            failed += 1

    summary = f"[WARN] {failed} of {len(files)} file(s) had problems" if failed else None
    if summary:
        progress.lines.append(summary)

    log_dir = Path.cwd()  # always where the script was invoked, regardless of -O
    if args.L:
        log_path = safe_name(log_dir / "gallery.log")
        log_path.write_text("\n".join(progress.lines) + "\n", encoding="utf-8")
        print(f"[OK] Wrote log: {log_path}")

    error_lines = [line for line in progress.lines if line.startswith("[ERROR]") or line.startswith("[WARN]")]
    if error_lines:
        error_log_path = safe_name(log_dir / "gallery_errors.log")
        error_log_path.write_text("\n".join(error_lines) + "\n", encoding="utf-8")
        print(f"[OK] Wrote error log: {error_log_path}")

    progress.clear()
    if summary:
        print(summary)
        sys.exit(1)


if __name__ == "__main__":
    main()

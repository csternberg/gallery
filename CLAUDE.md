# gallery

Single-file Python CLI (`gallery.py`) that builds a contact-sheet JPEG from a video: it pulls N evenly spaced frames with ffmpeg and tiles them with Pillow.

## Requirements
- Python 3.9+ (developed on 3.14), Pillow (`pip install pillow`)
- `ffmpeg` and `ffprobe` on PATH (checked in `main()`, not at import)

## Usage
```
python3 gallery.py [-C | -R] [-N 16] [-X px] [-Y px] [-F] [-M] [-O dir] [-L] [-j JOBS] [-V] [-h] [files/patterns...]
```
See [README.md](README.md) for the full switch table with descriptions. Quick reference:
- `-C` all files in cwd, `-R` recurse (alone = everything under cwd; with filenames = recursive globs)
- `-N` thumbnails per video, `-X`/`-Y` total gallery size in px (one given = the other follows the aspect ratio, both = non-proportional stretch)
- `-F` also save individual thumbnails to `<name>_thumbs/`, `-M` metadata bar above the grid (font scales with gallery width, see below)
- `-O dir` write the gallery and `-F` thumbs into `dir` instead of next to each source video (does **not** affect where `-L`/error logs go, see below)
- `-L` write exactly one full run log (`gallery.log`), always in the folder `gallery.py` was invoked from — never `-O`'s folder. Exactly one error log (`gallery_errors.log`) is written there too, automatically, whenever a problem occurs, `-L` or not (both are per-*run*, not per-file)
- `-j` parallel ffmpeg processes per video (default min(8, CPUs))
- `-V` print `VERSION` and exit, `-h` show help and exit
- Every short switch works in either case (`-n`/`-N`, `-o`/`-O`, `-j`/`-J`, `-h`/`-H`, `-v`/`-V`, …) — implemented by giving `add_argument` both option strings, and (for `-h`/`-V`) disabling argparse's built-in `add_help` to add a case-insensitive help action ourselves.
- Output: `<name>_gallery.jpg` next to the video (or in `-O`'s folder). `gallery.log`/`gallery_errors.log` always go next to where the script was run, regardless of `-O`. Existing files are never overwritten; a `_01`, `_02`… suffix is added.

## Design notes
- One `ffprobe` JSON call per file (`probe_video`) gives stream index, duration and metadata. It ignores attached-picture (cover art) streams.
- Frames are extracted with parallel `ffmpeg -ss <t> -i ...` calls (fast seek, one frame each) into a temp dir. `_extract_one` treats "exit 0 but no file written" as a failure, which happens when a seek lands past the end.
- `make_gallery` lays out the grid from the frames that actually exist, not from `-N`.
- `metadata_layout(total_x)` scales the `-M` header's font size/line height/padding with the gallery's final width (floor: the original fixed 16px/22px/10px, at `total_x<=~880`) so the header stays readable instead of looking tiny once galleries get past ~1000px wide.
- `Progress` draws a per-file `[i/N] name [####---] k/N thumbnails` line on a TTY and plain `[INFO]` lines otherwise. Route anything printed mid-file through `progress.log()` so it doesn't corrupt the live line. It also now keeps `self.lines`, the full transcript across every file in the run, written out once at the end (not per-file) to `gallery.log`/`gallery_errors.log`.
- Exit code is 1 if any file failed or had frame errors.
- `SKIP_EXTENSIONS` includes `.log`/`.lst`/`.txt` so `-C`/`-R` won't try to treat `gallery.py`'s own log output (or other stray text lists) as video files.

## Tests
`tests/` is a pytest suite (64 tests) covering `gallery.py`, added 2026-09-27 on a machine with real `ffmpeg`/`ffprobe` (7.1.1-full_build), then extended the same day for the `-V`/`-O`/`-L`/case-insensitivity/metadata-scaling additions. No fake shims: `tests/conftest.py` generates small synthetic fixtures (`testsrc`/`sine` via `ffmpeg -f lavfi`) once per session and every test exercises the real binaries.
```
pip install -r requirements-dev.txt
python -m pytest
```
- `test_helpers.py` — pure functions (`safe_name`, `is_potential_video`, `format_duration`, `_to_float`, `positive_int`, `find_videos`, `metadata_layout`), no ffmpeg needed.
- `test_progress.py` — `Progress` line drawing/clearing on tty vs non-tty streams, no ffmpeg needed.
- `test_probe.py` — `probe_video` against real ffprobe: mp4, mkv, attached-pic cover art (skipped), audio-only, corrupt file, missing file.
- `test_extract.py` — `extract_thumbnails`/`_extract_one` against real ffmpeg on mp4 and mkv, plus the "seek lands past the end" per-frame-error path.
- `test_gallery_build.py` — `make_gallery` sizing (`-X`/`-Y` combinations), metadata bar, `-F` thumbs saving, layout from frames-present, `safe_name` suffixing.
- `test_cli.py` — end-to-end subprocess runs: `-F -M`, rerun suffixing, corrupt/attached-pic files skipped without failing the batch, `[brackets]` filenames, `-R`, `-C`, missing-ffmpeg error path, clean non-tty output, `-X`/`-Y`, `-V`/`-v`/`-h`/`-H`, case-insensitive switches, `-O`, `-L` and the always-on error log, `.log` files not picked up as videos.

Rotated-phone-video auto-rotation is intentionally **not** covered (out of scope per instruction): mp4/mkv extraction works (`test_extract.py`), but a synthetic rotated fixture couldn't be built via ffmpeg CLI on this machine (`-metadata:s:v:0 rotate=90`, `-c copy` remux, and `-bsf:v h264_metadata=rotate=90` all left frames unrotated) — `test_extract_thumbnails_autorotates_phone_video` stays `@pytest.mark.skip`ped with the details, and would need a real phone-shot clip to verify by hand if this is picked back up later.

Speed-vs-original comparison is still blocked: this checkout has no `.git`, so `git show e469266:gallery.py` isn't fetchable here.

## Not yet decided / possible follow-ups
- Could scale frames inside ffmpeg (`-vf scale`) to avoid writing full-size temp JPEGs. This would need to account for rotation metadata.

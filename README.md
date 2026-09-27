# gallery

A small command-line tool that turns a video into a contact-sheet JPEG: it pulls a
number of evenly spaced frames out with `ffmpeg` and tiles them into a single image
with Pillow, optionally with a metadata header and the individual thumbnail files
saved alongside it.

## Requirements
- Python 3.9+
- [Pillow](https://pypi.org/project/pillow/) (`pip install pillow`)
- `ffmpeg` and `ffprobe` available on `PATH`

## Usage
```
python3 gallery.py [options] [files/patterns...]
```
Video files can be given explicitly (with shell globs or wildcard patterns), or
selected with `-C` / `-R`:
```
python3 gallery.py clip.mp4 "*.mov"     # explicit files / patterns
python3 gallery.py -C                   # every video in the current folder
python3 gallery.py -R                   # every video under the current folder, recursively
python3 gallery.py -R "*.mp4"           # recursive glob(s)
```

For each video, `gallery.py` writes `<name>_gallery.jpg` next to the source file
(or in the folder given with `-O`). It never overwrites an existing file — a
`_01`, `_02`, … suffix is added instead.

## Switches
Every short switch accepts either case (`-n` and `-N` are equivalent) unless noted.

| Switch | Long form | Description |
|---|---|---|
| `-C` | | Process every video file in the current folder |
| `-R` | | Recurse into subfolders (everything under the cwd if no files/patterns are given, otherwise turns any patterns into recursive globs) |
| `-N n` | | Number of thumbnails per video (default: 16) |
| `-X px` | | Total gallery width in pixels. If only `-X` or only `-Y` is given, the other dimension follows the frames' aspect ratio; giving both stretches the frames non-proportionally |
| `-Y px` | | Total gallery height in pixels |
| `-F` | | Also save the individual (resized) thumbnails to a `<name>_thumbs/` folder |
| `-M` | | Add a metadata header (filename, duration, resolution, codecs, bitrate) above the grid. Its text scales up automatically on wide galleries so it stays readable |
| `-O dir` | `--output dir` | Save each gallery (and its `-F` thumbnails) in `dir` instead of next to the source video |
| `-L` | | Write one full run log to `gallery.log`, in the folder `gallery.py` was run from (not `-O`'s folder). One error log (`gallery_errors.log`) is written there automatically any time a problem occurs, whether or not `-L` was given |
| `-j n` | `--jobs n` | Parallel `ffmpeg` processes per video (default: `min(8, CPU count)`) |
| `-V` | `--version` | Print the version and exit |
| `-h` | `--help` | Show the full help message and exit |

`.jpg`/`.log`/`.txt`/`.lst` and other obviously-non-video extensions are always
skipped when discovering input files, so re-running `gallery.py -C` in a folder
that already has galleries and logs in it won't try to process them.

## Examples
```
# Contact sheet with metadata header and saved individual thumbnails
python3 gallery.py -M -F clip.mp4

# 24 thumbnails, 1600px wide, everything collected in ./galleries
python3 gallery.py -R -N 24 -X 1600 -O galleries

# Full run log plus a wide gallery
python3 gallery.py -C -L -X 1920 -M
```

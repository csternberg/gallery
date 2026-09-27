from PIL import Image

import gallery
from conftest import requires_ffmpeg


def _thumbs(media_dir, tmp_path, count=4):
    info = gallery.probe_video(media_dir / "plain.mp4")
    files, errors = gallery.extract_thumbnails(
        media_dir / "plain.mp4", info["index"], info["duration"], count, tmp_path, jobs=2)
    assert not errors
    return files, info


@requires_ffmpeg
def test_make_gallery_default_size_from_frames(media_dir, tmp_path):
    thumbs, _ = _thumbs(media_dir, tmp_path)
    out = gallery.make_gallery(thumbs, tmp_path / "out.jpg")
    assert out is not None
    with Image.open(out) as img:
        assert img.size == (320 * 2, 240 * 2)  # 4 thumbs -> 2x2 grid of 320x240 frames


@requires_ffmpeg
def test_make_gallery_total_x_only_follows_aspect_ratio(media_dir, tmp_path):
    thumbs, _ = _thumbs(media_dir, tmp_path)
    out = gallery.make_gallery(thumbs, tmp_path / "out.jpg", total_x=640)
    with Image.open(out) as img:
        assert img.size == (640, 480)


@requires_ffmpeg
def test_make_gallery_total_y_only_follows_aspect_ratio(media_dir, tmp_path):
    thumbs, _ = _thumbs(media_dir, tmp_path)
    out = gallery.make_gallery(thumbs, tmp_path / "out.jpg", total_y=120)
    with Image.open(out) as img:
        assert img.size == (160, 120)


@requires_ffmpeg
def test_make_gallery_both_x_and_y_stretches(media_dir, tmp_path):
    thumbs, _ = _thumbs(media_dir, tmp_path)
    out = gallery.make_gallery(thumbs, tmp_path / "out.jpg", total_x=200, total_y=100)
    with Image.open(out) as img:
        assert img.size == (200, 100)


@requires_ffmpeg
def test_make_gallery_with_metadata_adds_header_only(media_dir, tmp_path):
    thumbs, info = _thumbs(media_dir, tmp_path)
    out_plain = gallery.make_gallery(thumbs, tmp_path / "plain_out.jpg")
    out_meta = gallery.make_gallery(thumbs, tmp_path / "meta_out.jpg", metadata=info["meta"])
    with Image.open(out_plain) as a, Image.open(out_meta) as b:
        assert b.size[0] == a.size[0]
        assert b.size[1] > a.size[1]


@requires_ffmpeg
def test_make_gallery_metadata_header_is_fixed_size_by_default(media_dir, tmp_path):
    # scale_text defaults to False (-S not given): header height shouldn't grow
    # with gallery width. total_y is given explicitly so the frame area's height
    # is identical between runs and any extra height is purely the header.
    thumbs, info = _thumbs(media_dir, tmp_path)
    narrow = gallery.make_gallery(
        thumbs, tmp_path / "narrow.jpg", total_x=320, total_y=480, metadata=info["meta"])
    wide = gallery.make_gallery(
        thumbs, tmp_path / "wide.jpg", total_x=1600, total_y=480, metadata=info["meta"])
    expected_header = 2 * 10 + 22 * 6  # fixed pad/line-height regardless of width
    with Image.open(narrow) as a, Image.open(wide) as b:
        assert a.size[1] - 480 == b.size[1] - 480 == expected_header


@requires_ffmpeg
def test_make_gallery_scale_text_grows_header_on_wide_gallery(media_dir, tmp_path):
    thumbs, info = _thumbs(media_dir, tmp_path)
    unscaled = gallery.make_gallery(
        thumbs, tmp_path / "unscaled.jpg", total_x=1600, metadata=info["meta"], scale_text=False)
    scaled = gallery.make_gallery(
        thumbs, tmp_path / "scaled.jpg", total_x=1600, metadata=info["meta"], scale_text=True)
    with Image.open(unscaled) as a, Image.open(scaled) as b:
        assert a.size[0] == b.size[0] == 1600
        assert b.size[1] > a.size[1]


@requires_ffmpeg
def test_make_gallery_saves_individual_resized_thumbs(media_dir, tmp_path):
    thumbs, _ = _thumbs(media_dir, tmp_path)
    thumbs_dir = tmp_path / "saved_thumbs"
    gallery.make_gallery(thumbs, tmp_path / "out.jpg", thumbs_dir=thumbs_dir)
    saved = sorted(thumbs_dir.glob("*.jpg"))
    assert len(saved) == len(thumbs)


@requires_ffmpeg
def test_make_gallery_uses_frames_present_not_dash_n(media_dir, tmp_path):
    # Only 3 of a requested 4 frames "survive" -> layout must be based on 3, not 4.
    thumbs, _ = _thumbs(media_dir, tmp_path, count=4)
    out = gallery.make_gallery(thumbs[:3], tmp_path / "out.jpg")
    with Image.open(out) as img:
        # ceil(sqrt(3))=2 cols, ceil(3/2)=2 rows
        assert img.size == (320 * 2, 240 * 2)


def test_make_gallery_returns_none_when_no_image_opens(tmp_path):
    bogus = tmp_path / "bogus.jpg"
    bogus.write_bytes(b"not an image")
    assert gallery.make_gallery([bogus], tmp_path / "out.jpg") is None


@requires_ffmpeg
def test_make_gallery_respects_safe_name(media_dir, tmp_path):
    thumbs, _ = _thumbs(media_dir, tmp_path)
    target = tmp_path / "out.jpg"
    target.write_bytes(b"existing")
    out = gallery.make_gallery(thumbs, target)
    assert out == tmp_path / "out_01.jpg"

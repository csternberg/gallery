import argparse
from pathlib import Path

import pytest

import gallery


def test_safe_name_no_conflict(tmp_path):
    target = tmp_path / "gallery.jpg"
    assert gallery.safe_name(target) == target


def test_safe_name_increments_past_existing(tmp_path):
    target = tmp_path / "gallery.jpg"
    target.write_bytes(b"x")
    (tmp_path / "gallery_01.jpg").write_bytes(b"x")
    assert gallery.safe_name(target) == tmp_path / "gallery_02.jpg"


def test_is_potential_video():
    assert gallery.is_potential_video(Path("clip.mp4"))
    assert gallery.is_potential_video(Path("clip.MKV"))  # case-insensitive
    assert gallery.is_potential_video(Path("clip.m4a"))  # may contain real video, not skipped
    assert not gallery.is_potential_video(Path("notes.txt"))
    assert not gallery.is_potential_video(Path("cover.JPG"))
    assert not gallery.is_potential_video(Path("song.mp3"))
    assert not gallery.is_potential_video(Path("gallery.log"))  # gallery's own -L output
    assert not gallery.is_potential_video(Path("gallery_errors.log"))
    assert not gallery.is_potential_video(Path("videos.lst"))


def test_metadata_layout_floors_at_original_fixed_values():
    # A narrow gallery keeps the pre-scaling defaults (16px font / 22px line / 10px pad).
    assert gallery.metadata_layout(320) == (16, 22, 10)


def test_metadata_layout_scales_up_with_width():
    small = gallery.metadata_layout(320)
    wide = gallery.metadata_layout(1600)
    assert wide[0] > small[0]  # font size
    assert wide[1] > small[1]  # line height
    assert wide[2] > small[2]  # padding


def test_format_duration():
    assert gallery.format_duration(None) == "Unknown"
    assert gallery.format_duration(65) == "00:01:05"
    assert gallery.format_duration(3661) == "01:01:01"
    assert gallery.format_duration(0) == "00:00:00"


def test_to_float():
    assert gallery._to_float("12.5") == 12.5
    assert gallery._to_float(0) is None
    assert gallery._to_float(-5) is None
    assert gallery._to_float("nan") is None
    assert gallery._to_float(None) is None
    assert gallery._to_float("not a number") is None


def test_positive_int_accepts_positive():
    assert gallery.positive_int("3") == 3


def test_positive_int_rejects_zero_and_negative():
    with pytest.raises(argparse.ArgumentTypeError):
        gallery.positive_int("0")
    with pytest.raises(argparse.ArgumentTypeError):
        gallery.positive_int("-1")


def test_find_videos_filters_and_sorts(tmp_path):
    (tmp_path / "b.mp4").write_bytes(b"")
    (tmp_path / "a.MOV").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")
    videos = gallery.find_videos([str(tmp_path / "*")])
    assert [p.name for p in videos] == ["a.MOV", "b.mp4"]


def test_find_videos_dedupes_overlapping_patterns(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"")
    pattern = str(tmp_path / "*")
    videos = gallery.find_videos([pattern, pattern])
    assert len(videos) == 1


def test_find_videos_literal_bracket_path_bypasses_glob(tmp_path):
    f = tmp_path / "clip[1].mp4"
    f.write_bytes(b"")
    videos = gallery.find_videos([str(f)])
    assert videos == [f]


def test_find_videos_recursive_pattern(tmp_path):
    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "d.mp4").write_bytes(b"")
    (tmp_path / "top.mp4").write_bytes(b"")
    pattern = str(tmp_path / "**" / "*")
    videos = gallery.find_videos([pattern], recursive=True)
    names = {p.name for p in videos}
    assert {"d.mp4", "top.mp4"} <= names


def test_find_videos_ignores_directories(tmp_path):
    (tmp_path / "looks_like_a_video.mp4").mkdir()
    videos = gallery.find_videos([str(tmp_path / "*")])
    assert videos == []

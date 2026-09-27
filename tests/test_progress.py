import io

import gallery


def _non_tty_stream():
    stream = io.StringIO()
    stream.isatty = lambda: False
    return stream


def _tty_stream():
    stream = io.StringIO()
    stream.isatty = lambda: True
    return stream


def test_non_tty_prints_plain_info_lines_and_no_ansi():
    stream = _non_tty_stream()
    p = gallery.Progress(stream)
    p.start(1, 3, "clip.mp4")
    p.update(1, 4)  # update is a no-op off a tty
    p.log("[OK] done")
    out = stream.getvalue()
    assert "[INFO] [1/3] clip.mp4" in out
    assert "[OK] done" in out
    assert "\x1b[" not in out


def test_tty_draws_progress_bar_and_clears():
    stream = _tty_stream()
    p = gallery.Progress(stream)
    p.start(1, 1, "clip.mp4")
    assert p.visible
    p.update(2, 4)
    out = stream.getvalue()
    assert "\x1b[K" in out
    assert "2/4 thumbnails" in out
    p.clear()
    assert not p.visible


def test_tty_log_clears_line_before_printing():
    stream = _tty_stream()
    p = gallery.Progress(stream)
    p.start(1, 1, "clip.mp4")
    p.log("[ERROR] boom")
    assert not p.visible
    assert "[ERROR] boom" in stream.getvalue()


def test_long_name_is_truncated_to_fit_terminal_width(monkeypatch):
    stream = _tty_stream()
    monkeypatch.setattr(gallery.shutil, "get_terminal_size", lambda fallback: type(
        "Size", (), {"columns": 40}
    )())
    p = gallery.Progress(stream)
    long_name = "a_very_long_filename_that_will_not_fit_on_forty_columns.mp4"
    p.start(1, 1, long_name)
    out = stream.getvalue()
    assert long_name not in out
    assert "..." in out

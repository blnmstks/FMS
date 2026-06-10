from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_extract_last_frame_builds_ffmpeg_command(tmp_path):
    from app.utils.video import extract_last_frame

    out = tmp_path / "last.png"
    with patch("app.utils.video.subprocess.run") as run:
        extract_last_frame("clip.mp4", str(out))

    argv = run.call_args.args[0]
    assert argv[0] == "ffmpeg"
    for flag in ("-sseof", "-0.1", "-update", "1", "-q:v"):
        assert flag in argv
    # вход идёт сразу после -i, выход — последний аргумент
    assert argv[argv.index("-i") + 1] == "clip.mp4"
    assert argv[-1] == str(out)


@pytest.mark.unit
def test_extract_last_frame_uses_check_true(tmp_path):
    from app.utils.video import extract_last_frame

    out = tmp_path / "last.png"
    with patch("app.utils.video.subprocess.run") as run:
        extract_last_frame("clip.mp4", str(out))

    assert run.call_args.kwargs.get("check") is True


@pytest.mark.unit
def test_extract_last_frame_creates_parent_dir(tmp_path):
    from app.utils.video import extract_last_frame

    out = tmp_path / "frames" / "last.png"
    with patch("app.utils.video.subprocess.run"):
        extract_last_frame("clip.mp4", str(out))

    assert out.parent.is_dir()


@pytest.mark.unit
def test_extract_last_frame_returns_output_path(tmp_path):
    from app.utils.video import extract_last_frame

    out = tmp_path / "last.png"
    with patch("app.utils.video.subprocess.run"):
        result = extract_last_frame("clip.mp4", str(out))

    assert result == str(out)

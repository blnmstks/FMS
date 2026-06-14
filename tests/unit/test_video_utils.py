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


@pytest.mark.unit
def test_ltx_snap_duration_observed_beat_durations():
    from app.utils.video import ltx_snap_duration

    # реальные длительности битов idea-1 → ближайшие валидные 8n+1-кадровые длительности
    assert ltx_snap_duration(4.6) == pytest.approx(14 * 8 / 24)
    assert ltx_snap_duration(3.48) == pytest.approx(11 * 8 / 24)
    assert ltx_snap_duration(3.8) == pytest.approx(4.0)
    assert ltx_snap_duration(4.04) == pytest.approx(13 * 8 / 24)


@pytest.mark.unit
def test_ltx_snap_duration_keeps_already_valid_duration():
    from app.utils.video import ltx_snap_duration

    assert ltx_snap_duration(3.0) == 3.0  # 72 кадра + 1 = 73 = 8*9+1


@pytest.mark.unit
def test_ltx_snap_duration_never_shrinks_and_yields_8n_plus_1_frames():
    from app.utils.video import ltx_snap_duration

    # инварианты 1, 2 и 4: snap >= вход; math-нода workflow (int(d*24+1)) даёт ровно 8n+1
    for n in range(1, 401):
        d = n * 8 / 24
        snapped = ltx_snap_duration(d)
        assert snapped == d  # валидная длительность не меняется (идемпотентность)
        assert int(snapped * 24 + 1) == 8 * n + 1
    for raw in (0.5, 1.7, 2.34, 5.01, 9.99):
        snapped = ltx_snap_duration(raw)
        assert snapped >= raw
        assert round(snapped * 24) % 8 == 0


@pytest.mark.unit
def test_ltx_snap_duration_tiny_input_yields_minimum_block():
    from app.utils.video import ltx_snap_duration

    assert ltx_snap_duration(0.0) == pytest.approx(8 / 24)
    assert ltx_snap_duration(0.01) == pytest.approx(8 / 24)


@pytest.mark.unit
def test_extract_frame_at_builds_ffmpeg_command(tmp_path):
    from app.utils.video import extract_frame_at

    out = tmp_path / "mid.png"
    with patch("app.utils.video.subprocess.run") as run:
        extract_frame_at("clip.mp4", 1.5, str(out))

    argv = run.call_args.args[0]
    assert argv[0] == "ffmpeg"
    # -ss идёт ДО -i (точный seek по входу), значение — str(seconds)
    assert argv[argv.index("-ss") + 1] == "1.5"
    assert argv.index("-ss") < argv.index("-i")
    assert argv[argv.index("-i") + 1] == "clip.mp4"
    assert "-frames:v" in argv
    assert argv[-1] == str(out)
    assert run.call_args.kwargs.get("check") is True


@pytest.mark.unit
def test_extract_frame_at_creates_parent_dir_and_returns_path(tmp_path):
    from app.utils.video import extract_frame_at

    out = tmp_path / "qc" / "mid.png"
    with patch("app.utils.video.subprocess.run"):
        result = extract_frame_at("clip.mp4", 0.0, str(out))

    assert out.parent.is_dir()
    assert result == str(out)


@pytest.mark.unit
def test_mux_clip_audio_builds_ffmpeg_command_and_replaces(tmp_path):
    from app.utils.video import mux_clip_audio

    clip = str(tmp_path / "clip.mp4")
    with (
        patch("app.utils.video.subprocess.run") as run,
        patch("app.utils.video.os.replace") as replace,
    ):
        result = mux_clip_audio(clip, "beat.wav")

    argv = run.call_args.args[0]
    assert argv[0] == "ffmpeg"
    # порядок входов: видео первым, WAV вторым
    i_positions = [i for i, a in enumerate(argv) if a == "-i"]
    assert argv[i_positions[0] + 1] == clip
    assert argv[i_positions[1] + 1] == "beat.wav"
    for flag in ("-map", "0:v:0"), ("-map", "1:a:0"), ("-c:v", "copy"), ("-c:a", "aac"):
        idx = [i for i, a in enumerate(argv) if a == flag[0]]
        assert any(argv[i + 1] == flag[1] for i in idx)
    assert argv[argv.index("-map_metadata") + 1] == "-1"
    # выход ffmpeg — tmp-файл, затем атомарная замена оригинала
    tmp_out = argv[-1]
    assert tmp_out != clip
    replace.assert_called_once_with(tmp_out, clip)
    assert run.call_args.kwargs.get("check") is True
    assert result == clip

import wave

import pytest


@pytest.mark.unit
def test_write_wav_writes_valid_header(tmp_path):
    from app.utils.audio import write_wav

    out = tmp_path / "out.wav"
    write_wav(b"\x00\x01" * 100, str(out))

    assert out.exists()
    with wave.open(str(out), "rb") as wf:
        assert wf.getframerate() == 24000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2


@pytest.mark.unit
def test_write_wav_creates_nested_dirs(tmp_path):
    from app.utils.audio import write_wav

    out = tmp_path / "a" / "b" / "x.wav"
    write_wav(b"\x00\x01" * 10, str(out))

    assert out.exists()


@pytest.mark.unit
def test_write_wav_returns_path(tmp_path):
    from app.utils.audio import write_wav

    out = tmp_path / "out.wav"
    result = write_wav(b"\x00\x01" * 10, str(out))

    assert result == str(out)


@pytest.mark.unit
def test_write_wav_respects_custom_params(tmp_path):
    from app.utils.audio import write_wav

    out = tmp_path / "out.wav"
    write_wav(b"\x00" * 80, str(out), sample_rate=48000, channels=2, sampwidth=2)

    with wave.open(str(out), "rb") as wf:
        assert wf.getframerate() == 48000
        assert wf.getnchannels() == 2


def _one_second_wav(path) -> str:
    # 24000 кадров при 24000 Hz, mono, 16-bit → ровно ~1000 мс.
    from app.utils.audio import write_wav

    return write_wav(b"\x00\x00" * 24000, str(path))


# --- wav_duration_ms ---


@pytest.mark.unit
def test_wav_duration_ms_returns_length(tmp_path):
    from app.utils.audio import wav_duration_ms

    src = _one_second_wav(tmp_path / "src.wav")
    assert abs(wav_duration_ms(src) - 1000) <= 10


# --- wav_duration_seconds ---


@pytest.mark.unit
def test_wav_duration_seconds_is_exact(tmp_path):
    from app.utils.audio import wav_duration_seconds, write_wav

    # 36000 кадров @ 24000 Hz = ровно 1.5 с (mono, 16-bit → 2 байта/кадр).
    src = write_wav(b"\x00\x00" * 36000, str(tmp_path / "src.wav"))

    assert wav_duration_seconds(src) == 1.5


@pytest.mark.unit
def test_wav_duration_seconds_not_rounded_to_ms(tmp_path):
    from app.utils.audio import wav_duration_seconds, write_wav

    # 24001 кадр @ 24000 Hz — нецелое число мс; результат точный, без округления до мс.
    src = write_wav(b"\x00\x00" * 24001, str(tmp_path / "src.wav"))

    assert wav_duration_seconds(src) == 24001 / 24000


# --- slice_wav ---


@pytest.mark.unit
def test_slice_wav_cuts_fragment(tmp_path):
    from app.utils.audio import slice_wav, wav_duration_ms

    src = _one_second_wav(tmp_path / "src.wav")
    dst = tmp_path / "clip.wav"
    slice_wav(src, str(dst), 200, 700)

    assert dst.exists()
    assert abs(wav_duration_ms(str(dst)) - 500) <= 20


@pytest.mark.unit
def test_slice_wav_creates_nested_dirs(tmp_path):
    from app.utils.audio import slice_wav

    src = _one_second_wav(tmp_path / "src.wav")
    dst = tmp_path / "beats" / "x.wav"
    slice_wav(src, str(dst), 0, 100)

    assert dst.exists()


@pytest.mark.unit
def test_slice_wav_returns_path(tmp_path):
    from app.utils.audio import slice_wav

    src = _one_second_wav(tmp_path / "src.wav")
    dst = tmp_path / "clip.wav"

    assert slice_wav(src, str(dst), 0, 100) == str(dst)

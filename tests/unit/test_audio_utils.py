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

from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import AUDIO_DIR, DEFAULT_TTS_VOICE, GEMINI_TTS_MODEL, SPEAKER_VOICE_MAP

# --- resolve_voice ---


@pytest.mark.unit
def test_resolve_voice_uses_map_for_known_speaker():
    from app.services.audio_tts import resolve_voice

    known = next(iter(SPEAKER_VOICE_MAP))
    assert resolve_voice(known) == SPEAKER_VOICE_MAP[known]


@pytest.mark.unit
def test_resolve_voice_falls_back_to_default():
    from app.services.audio_tts import resolve_voice

    assert resolve_voice("__not_in_map__") == DEFAULT_TTS_VOICE


@pytest.mark.unit
def test_resolve_voice_none_speaker_defaults():
    from app.services.audio_tts import resolve_voice

    assert resolve_voice(None) == DEFAULT_TTS_VOICE


# --- build_tts_prompt ---


@pytest.mark.unit
def test_build_tts_prompt_returns_tts_text_verbatim():
    from app.services.audio_tts import build_tts_prompt

    segment = {
        "seg_id": 11,
        "speaker": "Host",
        "emotion": "calm, reflective",
        "tts_text": "Welcome back, everyone.",
    }

    # эмоция/спикер в TTS-передаче не участвуют — промпт это ровно tts_text
    assert build_tts_prompt(segment) == "Welcome back, everyone."


@pytest.mark.unit
def test_build_tts_prompt_missing_text_returns_empty():
    from app.services.audio_tts import build_tts_prompt

    assert build_tts_prompt({}) == ""


# --- generate_segment_audio ---


@pytest.mark.unit
def test_generate_segment_audio_synthesizes_and_saves():
    from app.services.audio_tts import generate_segment_audio, resolve_voice

    segment = {
        "seg_id": 11,
        "speaker": "Host",
        "emotion": "excited",
        "tts_text": "Let's go!",
    }

    with (
        patch("app.services.audio_tts.synthesize", return_value=b"PCM") as synth,
        patch("app.services.audio_tts.write_wav", side_effect=lambda pcm, path: path) as wav,
    ):
        result = generate_segment_audio(segment, 7)

    # synthesize вызван с разрешённым голосом и моделью из конфига
    args, kwargs = synth.call_args
    called = list(args) + list(kwargs.values())
    assert resolve_voice("Host") in called
    assert GEMINI_TTS_MODEL in called

    # write_wav получил PCM от synthesize и путь под AUDIO_DIR с idea-7-seg-11
    wav_args, _ = wav.call_args
    assert wav_args[0] == b"PCM"
    out_path = wav_args[1]
    assert out_path.startswith(str(Path(AUDIO_DIR)))
    assert "idea-7-seg-11" in out_path
    assert out_path.endswith(".wav")

    assert result == out_path

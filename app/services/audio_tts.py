import time
from pathlib import Path

from app.config import AUDIO_DIR, DEFAULT_TTS_VOICE, GEMINI_TTS_MODEL, SPEAKER_VOICE_MAP
from app.infrastructure.google_tts_client import synthesize
from app.utils.audio import write_wav


def resolve_voice(speaker: str) -> str:
    # speaker → пресетный голос Gemini; неизвестный/None спикер → DEFAULT_TTS_VOICE.
    return SPEAKER_VOICE_MAP.get(speaker, DEFAULT_TTS_VOICE)


def build_tts_prompt(segment: dict) -> str:
    # Что уходит в TTS за один проход. Пока — только текст реплики (эмоция/режиссёрское окружение
    # в TTS-передаче временно отключены; это точка их повторного включения).
    return segment.get("tts_text") or ""


def generate_segment_audio(segment: dict, idea_id: int) -> str:
    # Бизнес-логика шага 10 для одного сегмента: голос → промпт → синтез → WAV в AUDIO_DIR.
    # Возвращает путь к сохранённому файлу.
    voice = resolve_voice(segment.get("speaker"))
    prompt = build_tts_prompt(segment)
    pcm = synthesize(prompt, voice, GEMINI_TTS_MODEL)

    seg_id = segment.get("seg_id")
    name = f"idea-{idea_id}-seg-{seg_id}-{time.strftime('%Y%m%d-%H%M%S')}.wav"
    return write_wav(pcm, str(Path(AUDIO_DIR) / name))

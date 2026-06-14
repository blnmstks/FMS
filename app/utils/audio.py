import math
import wave
from pathlib import Path

from pydub import AudioSegment


def write_wav(
    pcm: bytes,
    output_path: str,
    sample_rate: int = 24000,
    channels: int = 1,
    sampwidth: int = 2,
) -> str:
    # Оборачивает сырые PCM-байты в WAV-контейнер и пишет в output_path, создавая родительские
    # директории. Дефолты — под выход Gemini TTS (PCM signed 16-bit LE, 24000 Hz, mono).
    # Возвращает output_path.
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return output_path


def wav_duration_ms(path: str) -> float:
    # Длительность аудиофайла в миллисекундах (pydub).
    return len(AudioSegment.from_file(path))


def wav_duration_seconds(path: str) -> float:
    # Сэмпл-точная длина WAV в секундах из заголовка: nframes / framerate. Без округления и без
    # pydub (wav_duration_ms квантуется до целых мс). Шаг 13 задаёт длину видео ровно по реальной
    # длине поданного аудиобита — иначе видео и звук рассинхронизируются.
    with wave.open(path, "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def pad_wav_to_duration(input_path: str, output_path: str, target_seconds: float) -> str:
    # Дописывает тишину в ХВОСТ WAV до target_seconds (вход уже не короче цели → копия как есть,
    # НЕ режет), создавая родительские директории. Возвращает output_path. Нужна шагу 13:
    # длительность видео снапится вверх до 8n+1 кадров (ltx_snap_duration), а TrimAudioDuration
    # в workflow умеет только резать — паддим WAV до snap-длительности, чтобы аудио- и
    # видео-латенты совпали и речь никогда не обрезалась.
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    audio = AudioSegment.from_file(input_path)
    deficit_ms = math.ceil(target_seconds * 1000 - len(audio))
    if deficit_ms > 0:
        audio += AudioSegment.silent(duration=deficit_ms, frame_rate=audio.frame_rate)
    audio.export(str(out), format="wav")
    return output_path


def slice_wav(input_path: str, output_path: str, start_ms: float, end_ms: float) -> str:
    # Вырезает фрагмент [start_ms:end_ms] из input_path и пишет его в output_path форматом wav,
    # создавая родительские директории. Возвращает output_path. (Как в slice_segment.py — pydub.)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    clip = AudioSegment.from_file(input_path)[start_ms:end_ms]
    clip.export(str(out), format="wav")
    return output_path

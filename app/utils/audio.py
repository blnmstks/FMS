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


def slice_wav(input_path: str, output_path: str, start_ms: float, end_ms: float) -> str:
    # Вырезает фрагмент [start_ms:end_ms] из input_path и пишет его в output_path форматом wav,
    # создавая родительские директории. Возвращает output_path. (Как в slice_segment.py — pydub.)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    clip = AudioSegment.from_file(input_path)[start_ms:end_ms]
    clip.export(str(out), format="wav")
    return output_path

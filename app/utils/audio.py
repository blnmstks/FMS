import wave
from pathlib import Path


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

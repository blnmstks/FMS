# Spec: `app/utils/audio`

Чистые утилиты для аудио-файлов. Без доменных знаний и без вызовов LLM/API.

## `write_wav(pcm: bytes, output_path: str, sample_rate: int = 24000, channels: int = 1, sampwidth: int = 2) -> str`

### Contract
Оборачивает сырые PCM-байты в WAV-контейнер (модуль `wave`) и пишет в `output_path`.
Создаёт родительские директории при необходимости. Возвращает `output_path`.

Дефолты соответствуют выходу Gemini TTS: PCM signed 16-bit LE (`sampwidth=2`), 24000 Hz, mono.

### Invariants
1. Создаёт `output_path.parent` (`mkdir(parents=True, exist_ok=True)`).
2. WAV-заголовок: `nchannels=channels`, `sampwidth=sampwidth`, `framerate=sample_rate`.
3. Возвращает строку `output_path`.

### Test cases (unit, `tmp_path`)
- **пишет корректный WAV**: после `write_wav(b"\x00\x01...", tmp/out.wav)` файл существует,
  `wave.open(...).getframerate() == 24000`, `getnchannels() == 1`, `getsampwidth() == 2`
- **создаёт вложенные папки**: `write_wav(pcm, tmp/"a"/"b"/"x.wav")` создаёт директории и файл
- **возвращает путь**: результат равен переданному `output_path`

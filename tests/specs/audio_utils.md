# Spec: `app/utils/audio`

Чистые утилиты для аудио-файлов. Без доменных знаний и без вызовов LLM/API.

`write_wav` работает на stdlib `wave`; `wav_duration_ms`/`slice_wav` — на `pydub`
(как в референсном `slice_segment.py`). `pydub` импортируется на уровне модуля (чистая
Python-зависимость; для WAV ffmpeg не требует).

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

## `wav_duration_ms(path: str) -> float`

### Contract
Длительность аудиофайла в миллисекундах — `len(AudioSegment.from_file(path))` (pydub).

### Test cases (unit, `tmp_path`)
- **длительность**: для WAV из 24000 кадров (24000 Hz, mono, 16-bit) `wav_duration_ms(path)`
  близка к `1000` (±10 мс)

## `wav_duration_seconds(path: str) -> float`

### Contract
Сэмпл-точная длина WAV в секундах из заголовка контейнера: `nframes / framerate` (stdlib
`wave`). Без округления и без `pydub` (в отличие от `wav_duration_ms`, который через `pydub`
квантуется до целых мс). Нужна шагу 13: длину видео задаём ровно по реальной длине поданного
аудиобита, иначе видео и звук рассинхронизируются.

### Invariants
1. Результат точно равен `nframes / framerate` прочитанного файла (без округления).
2. Открывает файл только на чтение и закрывает его (контекст-менеджер `wave.open`).

### Test cases (unit, `tmp_path`)
- **точная длина**: для WAV из ровно 36000 кадров @ 24000 Hz результат равен `1.5` (точно,
  без допуска)
- **отличается от ms-округления**: для нецелого числа мс (напр. 24001 кадр @ 24000 Hz)
  результат `24001/24000` совпадает сам с собой точно

## `slice_wav(input_path: str, output_path: str, start_ms: float, end_ms: float) -> str`

### Contract
Вырезает фрагмент `[start_ms:end_ms]` из `input_path` и пишет его в `output_path` форматом `wav`
(`AudioSegment.from_file(...)[start_ms:end_ms].export(output_path, format="wav")`). Создаёт
родительские директории при необходимости. Возвращает `output_path`. Границы — целые/дробные мс
(pydub принимает срез по мс).

### Invariants
1. Создаёт `output_path.parent` (`mkdir(parents=True, exist_ok=True)`).
2. Файл `output_path` существует после вызова, длительность ≈ `end_ms - start_ms`.
3. Возвращает строку `output_path`.

### Test cases (unit, `tmp_path`)
- **режет фрагмент**: из WAV длиной ~1000 мс `slice_wav(src, dst, 200, 700)` создаёт `dst`,
  его длительность ≈ 500 мс (±20 мс)
- **создаёт вложенные папки**: `slice_wav(src, tmp/"beats"/"x.wav", 0, 100)` создаёт директории
- **возвращает путь**: результат равен переданному `output_path`

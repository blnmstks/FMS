# Spec: `app/utils/video`

Чистые утилиты для видео-файлов. Без доменных знаний и без вызовов LLM/API. Обёртка над
`ffmpeg` через `subprocess` (как `infrastructure/aeneas_client` — системная зависимость ffmpeg).

## `extract_last_frame(video_path: str, output_path: str) -> str`

### Contract
Извлекает последний кадр видео в `output_path` (PNG) через `ffmpeg`. Команда:
`ffmpeg -y -sseof -0.1 -i <video_path> -update 1 -q:v 1 <output_path>`
- `-sseof -0.1` — позиционирование за 0.1 с до конца файла (берём самый последний кадр);
- `-update 1` — перезаписывать один и тот же выходной файл (а не последовательность);
- `-q:v 1` — максимальное качество PNG;
- `-y` — перезаписать выход без вопроса.
Создаёт родительскую директорию `output_path` при необходимости. `subprocess.run(..., check=True,
capture_output=True)` — ненулевой код возврата ffmpeg поднимает `CalledProcessError`. Возвращает
`output_path`. Нужна шагу 13: последний кадр клипа становится первым кадром следующего клипа
(сцепка мини-клипов без скачков).

### Invariants
1. Создаёт `Path(output_path).parent` (`mkdir(parents=True, exist_ok=True)`).
2. ffmpeg вызывается с флагами `-sseof -0.1`, `-update 1`, `-q:v 1` и путями `video_path`
   (вход, после `-i`) и `output_path` (последний аргумент).
3. `check=True` — ошибка ffmpeg пробрасывается (`CalledProcessError`).
4. Возвращает `output_path`.

### Test cases (unit, `subprocess.run` замокан, `tmp_path`)
- **командная строка**: argv содержит `ffmpeg`, `-sseof`, `-0.1`, `-update`, `1`, `-q:v`, `1`;
  `video_path` идёт сразу после `-i`; `output_path` — последний аргумент.
- **check=True**: `subprocess.run` вызван с `check=True`.
- **создаёт папку**: для `output_path` вида `tmp/frames/last.png` директория `frames` создаётся.
- **возвращает путь**: результат равен `output_path`.

## `ltx_snap_duration(seconds: float, fps: int = 24) -> float`

### Contract
Округляет длительность ВВЕРХ до ближайшей валидной для LTX-2.3: модель генерирует ровно
`8n+1` кадров; workflow считает кадры как `duration*fps+1` и НЕ-валидные значения молча
режутся ВНИЗ (наблюдалось: запрошено 4.6 с → получено 4.375 с, хвост речи без запаса по
тишине обрезался бы). Возвращает `ceil(seconds*fps/8) * 8 / fps` (минимум `8/fps`):
`snap*fps + 1 == 8n+1` и `snap >= seconds` — видео никогда не короче аудио.

### Invariants
1. `snap >= seconds` (видео не короче речи).
2. `int(snap*fps) % 8 == 0`, т.е. кадров будет `8n+1`.
3. Идемпотентность: `ltx_snap_duration(ltx_snap_duration(s)) == ltx_snap_duration(s)`.
4. Float-безопасность: для всех разумных n (1..400) `int(snap*fps + 1) == 8n+1` —
   воспроизводит целочисленное приведение в math-ноде workflow без потери кадра.

### Test cases (unit)
- **наблюдённые длительности битов**: 4.6→4.666…, 3.48→3.666…, 3.8→4.0, 3.0→3.0,
  4.04→4.333… (`pytest.approx`).
- **уже валидная длительность не меняется**: 3.0 (= 72 кадра + 1) → 3.0.
- **property-цикл**: для n=1..400, `d = 8n/24`: `ltx_snap_duration(d) == d` и
  `int(d*24 + 1) == 8n+1`.
- **ноль/крошечная длительность**: 0.0 и 0.01 → `8/24` (минимум один блок).

## `extract_frame_at(video_path: str, seconds: float, output_path: str) -> str`

### Contract
Извлекает один кадр на позиции `seconds` (PNG):
`ffmpeg -y -ss <seconds> -i <video_path> -frames:v 1 -q:v 1 <output_path>`.
Создаёт родительскую директорию; `check=True, capture_output=True`; возвращает
`output_path`. Нужна QC-гейту шага 13 (кадры first/mid клипа).

### Invariants
1. Создаёт `Path(output_path).parent`.
2. argv: `-ss` со строкой `seconds` ДО `-i` (точный seek по входу), `-frames:v 1`,
   `-q:v 1`; вход после `-i`; выход — последний аргумент.
3. `check=True`; возвращает `output_path`.

### Test cases (unit, `subprocess.run` замокан, `tmp_path`)
- **командная строка**: `-ss` присутствует, его значение == `str(seconds)`, индекс `-ss`
  меньше индекса `-i`; `-frames:v 1` присутствует; выход — последний аргумент.
- **check=True**, **создаёт папку**, **возвращает путь** — как у `extract_last_frame`.

## `mux_clip_audio(video_path: str, wav_path: str) -> str`

### Contract
Заменяет аудиодорожку клипа на оригинальный WAV и срезает метаданные — на месте:
`ffmpeg -y -i <video_path> -i <wav_path> -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac
-b:a 192k -map_metadata -1 -movflags +faststart <video_path стем>.tmp.mp4`,
затем `os.replace(tmp, video_path)`. Возвращает `video_path`.

Зачем: 1) ComfyUI отдаёт голос после прогона через Audio-VAE (нейрокодек туда-обратно —
деградация TTS); муксим исходный WAV бита. 2) `-map_metadata -1` срезает утечку полного
ComfyUI-графа (tag `prompt`) из публикуемого MP4. Видео может быть чуть длиннее аудио —
аудиопоток просто короче, `-shortest` НЕ используется (видео не режем).

### Invariants
1. Первый вход — `video_path`, второй — `wav_path`; `-map 0:v:0` и `-map 1:a:0`.
2. `-c:v copy` (видео не перекодируется), `-c:a aac`, `-map_metadata -1`.
3. Выход ffmpeg — временный файл, затем атомарный `os.replace(tmp, video_path)`;
   `video_path` остаётся единственным итоговым файлом.
4. `check=True`; возвращает `video_path`.

### Test cases (unit, `subprocess.run` и `os.replace` замоканы)
- **командная строка**: порядок входов, оба `-map`, `-c:v copy`, `-c:a aac`,
  `-map_metadata -1`; последний аргумент — tmp-путь (≠ `video_path`).
- **replace**: `os.replace` вызван с `(tmp, video_path)`.
- **check=True**; **возвращает `video_path`**.

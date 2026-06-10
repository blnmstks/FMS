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

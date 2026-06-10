# Spec: `app/services/comfyui`

Оркестрация генерации изображения (шаг 8) и видео-клипов (шаг 13) через ComfyUI: собирает
`utils/workflow` + `utils/audio` + `infrastructure/comfyui_client`. Решения и порядок шагов
живут здесь.

## `generate_image(workflow_path, prompt_text, prompt_node_id, output_path, image_path=None, image_node_id=None, poll_interval=1.0, timeout=DEFAULT_TIMEOUT) -> str`

`DEFAULT_TIMEOUT = 300.0` — дефолт подобран под медленные модели (Flux: загрузка модели +
сэмплинг легко дольше 30с). Слишком короткий таймаут приводит к `TimeoutError` до скачивания,
и копия в проект не пишется (хотя ComfyUI у себя картинку сохраняет нодой SaveImage).

### Contract
1. `wf = load_workflow(workflow_path)`.
2. `set_node_input(wf, prompt_node_id, "text", prompt_text)`.
3. Если задан `image_path`: `name = upload_image(image_path)["name"]`, затем
   `set_node_input(wf, image_node_id, "image", name)`.
4. `client_id = uuid4().hex`; `prompt_id = queue_prompt(wf, client_id)`.
5. Polling `get_history(prompt_id)` каждые `poll_interval` сек, пока в
   `history[prompt_id]["outputs"]` не появится выходной файл. По истечении `timeout` —
   `TimeoutError`.
6. Берётся первый выходной файл через `_first_output_file` (первая нода, первый элемент по
   ключу `images`/`gifs`/`videos`): `{filename, subfolder, type}`.
7. `data = download_image(filename, subfolder, type)`; байты пишутся в `output_path`
   (родительская папка создаётся при необходимости).
8. Возвращает `output_path`.

### Invariants
1. Промпт всегда подставляется в ноду `prompt_node_id` под ключ `text` до отправки.
2. `upload_image` вызывается **только** при непустом `image_path`; тогда имя файла
   пишется в `image_node_id` под ключ `image`.
3. Без `image_path` ни `upload_image` не вызывается, ни нода изображения не трогается.
4. В `output_path` записываются ровно байты, вернувшиеся из `download_image`.
5. Возвращается `output_path`.
6. Если за `timeout` результат не появился — поднимается `TimeoutError`, файл не пишется.

## `build_prompt_text(image_prompt: dict) -> str`

### Contract
Объединяет непустые поля сохранённого image-prompt в порядке `IMAGE_PROMPT_FIELDS`
(`image_prompt, camera_angle, lighting, mood, action`) через `", "`. Пустые/отсутствующие
поля пропускаются. Лишние ключи строки БД (`id`, `scenario`, `created_at`) игнорируются.

### Invariants
1. Порядок частей соответствует `IMAGE_PROMPT_FIELDS`.
2. Пустые значения (`None`/`""`) не попадают в результат.

## `generate_first_beat_image(image_prompt: dict, idea_id: int) -> str`

### Contract
Бизнес-логика генерации картинки первого бита: собирает текст через `build_prompt_text`,
резолвит путь под `IMAGES_DIR` (имя `idea-<idea_id>-first-beat-<timestamp>.png`) и делегирует
в `generate_image(COMFYUI_WORKFLOW, prompt_text, COMFYUI_PROMPT_NODE, out)`. Возвращает путь
сохранённого файла.

### Invariants
1. `generate_image` вызывается с workflow и node id из конфига (`COMFYUI_WORKFLOW`,
   `COMFYUI_PROMPT_NODE`) и `prompt_text == build_prompt_text(image_prompt)`.
2. `output_path` лежит под `IMAGES_DIR` и содержит `idea-<idea_id>`.
3. Возвращает то, что вернул `generate_image`.

## `resolve_output_path(out: str | None, workflow_path: str, images_dir: str) -> str`

### Contract
Решает, куда писать копию изображения в проекте:
- `out` задан и **абсолютный** → возвращается как есть;
- `out` задан и **относительный** → кладётся внутрь `images_dir` (`Path(images_dir) / out`);
- `out` пуст (`None`/`""`) → дефолтное имя `"<workflow-stem>-<timestamp>.png"` внутри
  `images_dir`.

### Invariants
1. Абсолютный `out` не модифицируется.
2. Относительный `out` всегда оказывается под `images_dir`.
3. При пустом `out` имя содержит stem workflow-файла и оканчивается на `.png`, путь — под
   `images_dir`.

## `_first_output_file(outputs: dict) -> dict | None`

### Contract
Возвращает первый выходной файл из `outputs` (значения нод) по любому из ключей
`images`/`gifs`/`videos`: `{filename, subfolder, type}`. Нужен, потому что нода SaveVideo
кладёт результат под ключ, отличный от `images` (у картинок — `images`). Если файлов нет —
`None`. Общий для `generate_image` и `generate_beat_clip` (через `_wait_for_output`).

### Invariants
1. Перебор нод в порядке `outputs.values()`, ключей — `images`→`gifs`→`videos`.
2. Возвращает первый непустой `files[0]` либо `None`.

## `build_video_prompt_text(video_beat_prompt: dict) -> str`

### Contract
Объединяет непустые поля видео-промпта бита в порядке `VIDEO_PROMPT_FIELDS`
(`video_prompt`, `end_frame`) через `", "` (как `build_prompt_text` для картинок). Пустые/
отсутствующие поля пропускаются; лишние ключи строки БД (`id`, `beat`) игнорируются.
Изолирована намеренно — точная «сцепка» промпта будет дорабатываться.

### Invariants
1. Порядок частей соответствует `VIDEO_PROMPT_FIELDS`.
2. Пустые значения (`None`/`""`) не попадают в результат.

## `generate_beat_clip(prompt_text, first_frame_path, audio_path, idea_id, beat_id, poll_interval=1.0, timeout=DEFAULT_VIDEO_TIMEOUT) -> str`

`DEFAULT_VIDEO_TIMEOUT = 1800.0` — видео медленнее картинки (LTX-2.3: загрузка + сэмплинг +
апскейл).

### Contract
Бизнес-логика генерации видео-клипа одного бита (шаг 13):
1. `wf = load_workflow(COMFYUI_VIDEO_WORKFLOW)`.
2. `set_node_input(wf, COMFYUI_VIDEO_PROMPT_NODE, "value", prompt_text)`.
3. `name = upload_image(first_frame_path)["name"]`; `set_node_input(wf,
   COMFYUI_VIDEO_IMAGE_NODE, "image", name)`.
4. `name = upload_audio(audio_path)["name"]`; `set_node_input(wf, COMFYUI_VIDEO_AUDIO_NODE,
   "audio", name)`.
5. `set_node_input(wf, COMFYUI_VIDEO_DURATION_NODE, "value", wav_duration_seconds(audio_path))`
   — точная длина того же файла, что заливаем (длина видео = длина аудио, без рассинхрона).
6. `prompt_id = queue_prompt(wf, uuid4().hex)`; ждём `_wait_for_output(...)`.
7. `data = download_image(filename, subfolder, type)`; пишем в
   `VIDEOS_DIR/clips/idea-<idea_id>-beat-<beat_id>-<timestamp><ext>` (ext — из имени файла
   ComfyUI, иначе `.mp4`), создавая папку. Возвращает путь.

### Invariants
1. Промпт всегда в `COMFYUI_VIDEO_PROMPT_NODE["value"]`; первый кадр через `upload_image` в
   `COMFYUI_VIDEO_IMAGE_NODE["image"]`; аудио через `upload_audio` в
   `COMFYUI_VIDEO_AUDIO_NODE["audio"]`.
2. В `COMFYUI_VIDEO_DURATION_NODE["value"]` кладётся ровно `wav_duration_seconds(audio_path)`
   (без округления).
3. В выходной файл пишутся ровно байты `download_image`; путь — под `VIDEOS_DIR/clips` и
   содержит `idea-<idea_id>-beat-<beat_id>`.
4. Если за `timeout` результат не появился — `TimeoutError`, файл не пишется.

## Runnable-скрипт (`python -m app.services.comfyui`)
`argparse`: `--workflow`, `--prompt`, `--prompt-node` (обязательные); `--out`, `--image`,
`--image-node`, `--timeout` (опциональные, `--timeout` по умолчанию `DEFAULT_TIMEOUT`).
Путь резолвится через `resolve_output_path(args.out, args.workflow, IMAGES_DIR)` (по умолчанию
копия идёт в `assets/images`), затем вызывается `generate_image(...)` и печатается путь.

## Test cases (unit; функции клиента замоканы, файлы через `tmp_path`)
- **подставляет промпт**: `queue_prompt` получил workflow с `["<prompt-node>"]["inputs"]["text"] == prompt_text`.
- **с image_path**: `upload_image` вызван с путём; `["<image-node>"]["inputs"]["image"]` == возвращённое имя.
- **без image_path**: `upload_image` не вызван.
- **сохраняет файл**: в `output_path` лежат байты из `download_image`; функция вернула `output_path`.
- **resolve абсолютный**: `resolve_output_path("/abs/x.png", wf, "assets/images") == "/abs/x.png"`.
- **resolve относительный**: `resolve_output_path("x.png", wf, "assets/images")` → `assets/images/x.png`.
- **resolve дефолт**: `resolve_output_path(None, ".../portrait_001.json", "assets/images")` →
  начинается с `assets/images`, содержит `portrait_001`, оканчивается на `.png`.
- **build_prompt_text**: для строки со всеми полями → части в порядке полей через ", ";
  пустые поля пропускаются.
- **generate_first_beat_image**: `patch` `generate_image` → вызван с `COMFYUI_WORKFLOW`,
  `COMFYUI_PROMPT_NODE`, `prompt_text == build_prompt_text(...)`, `output_path` под `IMAGES_DIR`
  и содержит `idea-7`; возврат пробрасывается.
- **_first_output_file**: находит файл под `gifs`/`videos` (не только `images`); пустые
  `outputs` → `None`.
- **build_video_prompt_text**: для строки со всеми полями → части в порядке
  `VIDEO_PROMPT_FIELDS` через ", "; пустые поля пропускаются.
- **generate_beat_clip** (моки клиента, реальный мини-WAV, `VIDEOS_DIR`/`COMFYUI_VIDEO_WORKFLOW`
  замоканы на `tmp_path`): промпт в prompt-ноде; `upload_image`(first_frame)+image-нода;
  `upload_audio`(audio)+audio-нода; duration-нода == `wav_duration_seconds(audio)` (точно);
  байты из `download_image` записаны под `VIDEOS_DIR/clips/...`, путь содержит
  `idea-<id>-beat-<id>`; пустой `outputs` → `TimeoutError`, файл не пишется.

# Spec: `app/services/comfyui`

Оркестрация генерации изображения через ComfyUI: собирает `utils/workflow` +
`infrastructure/comfyui_client`. Решения и порядок шагов живут здесь.

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
   `history[prompt_id]["outputs"]` не появятся данные. По истечении `timeout` —
   `TimeoutError`.
6. Берётся первое изображение из `outputs` (первая нода, её первый элемент `images`):
   `{filename, subfolder, type}`.
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

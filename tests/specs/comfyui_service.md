# Spec: `app/services/comfyui`

Оркестрация генерации изображения через ComfyUI: собирает `utils/workflow` +
`infrastructure/comfyui_client`. Решения и порядок шагов живут здесь.

## `generate_image(workflow_path, prompt_text, prompt_node_id, output_path, image_path=None, image_node_id=None, poll_interval=1.0, timeout=120.0) -> str`

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

## Runnable-скрипт (`python -m app.services.comfyui`)
`argparse`: `--workflow`, `--prompt`, `--prompt-node`, `--out` (обязательные),
`--image`, `--image-node` (опциональные). Вызывает `generate_image(...)` и печатает путь.

## Test cases (unit; функции клиента замоканы, файлы через `tmp_path`)
- **подставляет промпт**: `queue_prompt` получил workflow с `["<prompt-node>"]["inputs"]["text"] == prompt_text`.
- **с image_path**: `upload_image` вызван с путём; `["<image-node>"]["inputs"]["image"]` == возвращённое имя.
- **без image_path**: `upload_image` не вызван.
- **сохраняет файл**: в `output_path` лежат байты из `download_image`; функция вернула `output_path`.

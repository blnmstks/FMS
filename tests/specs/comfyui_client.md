# Spec: `app/infrastructure/comfyui_client`

Только HTTP-транспорт к локальному ComfyUI (`requests`). Без бизнес-логики: каждая
функция — ровно один HTTP-запрос; решение «готово ли» и циклы ожидания живут в сервисе.

Базовый URL берётся из `app.config.COMFYUI_URL` (например `http://127.0.0.1:8188`).

## `upload_image(image_path: str) -> dict`

### Contract
`POST {COMFYUI_URL}/upload/image` как multipart-форма с файлом в поле `image`
(имя файла = имя из пути). Возвращает распарсенный JSON ответа ComfyUI
`{"name", "subfolder", "type"}`.

### Invariants
1. URL = `{COMFYUI_URL}/upload/image`, метод POST.
2. Файл передаётся в `files={"image": (...)}`.
3. Возвращает `response.json()` (dict), не модифицирует его.

## `upload_audio(audio_path: str) -> dict`

### Contract
То же, что `upload_image`, но для аудиофайла: `/upload/image` — общий input-upload ComfyUI,
принимает любой файл в input-каталог (нода LoadAudio затем берёт его по имени). Поле формы —
тоже `image` (имя поля эндпоинта, не тип медиа). Возвращает `{"name", "subfolder", "type"}`.
`upload_image`/`upload_audio` делят единственную транспортную реализацию.

### Invariants
1. URL = `{COMFYUI_URL}/upload/image`, метод POST, файл в `files={"image": (...)}`.
2. Возвращает `response.json()` (dict).

## `queue_prompt(workflow: dict, client_id: str) -> str`

### Contract
`POST {COMFYUI_URL}/prompt` с JSON-телом `{"prompt": workflow, "client_id": client_id}`.
Возвращает `prompt_id` из ответа.

### Invariants
1. URL = `{COMFYUI_URL}/prompt`, метод POST, `json=` содержит ключи `prompt` и `client_id`.
2. `workflow` передаётся без изменений под ключом `prompt`.
3. Возвращает строку `response.json()["prompt_id"]`.

## `get_history(prompt_id: str) -> dict`

### Contract
`GET {COMFYUI_URL}/history/{prompt_id}`. Возвращает распарсенный JSON
(`{prompt_id: {"outputs": {...}, "status": {...}}}` либо `{}`, если ещё не готово).

### Invariants
1. URL = `{COMFYUI_URL}/history/{prompt_id}`, метод GET.
2. Возвращает `response.json()` как есть.

## `download_image(filename: str, subfolder: str, folder_type: str) -> bytes`

### Contract
`GET {COMFYUI_URL}/view` с query-параметрами `filename`, `subfolder`, `type=folder_type`.
Возвращает сырые байты изображения (`response.content`).

### Invariants
1. URL = `{COMFYUI_URL}/view`, метод GET.
2. `params` содержит `filename`, `subfolder`, `type`.
3. Возвращает `response.content` (bytes).

## Общие инварианты
- Все функции вызывают `response.raise_for_status()` перед возвратом (ошибки транспорта
  всплывают наружу, сервис их не глотает).

## Test cases (unit, `requests` замокан)
- **upload_image**: дергает POST `/upload/image`, в `files` есть ключ `image`; возвращает
  dict из `response.json()`.
- **upload_audio**: дергает POST `/upload/image` (тот же эндпоинт), в `files` есть ключ
  `image`; возвращает dict из `response.json()`.
- **queue_prompt**: POST `/prompt` с `json={"prompt": <wf>, "client_id": "abc"}`; возвращает
  `"pid-1"` из `{"prompt_id": "pid-1"}`.
- **get_history**: GET `/history/pid-1`; возвращает тело ответа как dict.
- **download_image**: GET `/view` с `params={"filename","subfolder","type"}`; возвращает байты.

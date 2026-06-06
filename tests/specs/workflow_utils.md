# Spec: `app/utils/workflow`

Чистые JSON-хелперы для ComfyUI API-format workflow. Без HTTP, без LLM, без домена:
generic-загрузка и патч вложенного словаря по node id.

API-format workflow — это `dict`, ключи которого строковые id нод, каждая нода имеет
`class_type` и `inputs` (словарь входов).

## `load_workflow(path: str) -> dict`

### Contract
Читает файл (через `read_text_file` из `app/utils/files.py`) и парсит его как JSON.
Возвращает dict workflow.

### Invariants
1. Возвращает результат `json.loads` содержимого файла.
2. Не модифицирует файл.

## `set_node_input(workflow: dict, node_id: str, key: str, value) -> dict`

### Contract
Записывает `workflow[node_id]["inputs"][key] = value` и возвращает тот же `workflow`.
Какой именно `key` (`text`/`image`/…) — решает вызывающий код (сервис).

### Invariants
1. После вызова `workflow[node_id]["inputs"][key] == value`.
2. Прочие ноды и прочие входы целевой ноды не меняются.
3. Возвращает тот же объект `workflow`.

## Test cases (unit)
- **load_workflow**: записать JSON в `tmp_path`, прочитать — получить эквивалентный dict.
- **set_node_input**: на `{"6": {"inputs": {"text": "old"}}, "9": {...}}` вызов
  `set_node_input(wf, "6", "text", "new")` → `wf["6"]["inputs"]["text"] == "new"`,
  нода `"9"` не тронута, возвращён тот же объект.

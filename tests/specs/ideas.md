# Spec: `app/services/ideas`

## `generate_video_ideas(channel_name, channel_description, channel_style, transcript_texts) -> list[str]`

### Contract
Генерирует видео-идеи в стиле канала через LLM.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `channel_name` | `str` | имя канала |
| `channel_description` | `str` | описание канала |
| `channel_style` | `dict` | поля стиля (как минимум ключи из `IDEA_STYLE_FIELDS`) |
| `transcript_texts` | `list[str]` | содержимое транскриптов |

Собирает user-content из `GENERATE_VIDEO_IDEAS_PROMPT` + имя/описание канала + 13 полей
стиля (`IDEA_STYLE_FIELDS` — все `STYLE_FIELDS` кроме `average_word_count`) + транскрипты.
Вызывает `get_client().chat.completions.create(...)` с `response_format={"type": "json_object"}`,
печатает usage, парсит ответ через `json.JSONDecoder().raw_decode(...)`.

Ожидаемый JSON-ответ LLM: `{"ideas": ["idea 1", ..., "idea 10"]}`.

Возвращает `data["ideas"]` — список строк.

### `IDEA_STYLE_FIELDS`
`niche`, `target_audience`, `hook_style`, `script_flow`, `sentence_rhythm`, `tone`,
`transitions`, `curiosity_gaps`, `emotional_triggers`, `retention_techniques`,
`direct_address`, `words_per_second`, `target_word_count`.

### Invariants
1. Возвращает список ровно из тех идей, что прислал LLM (10 при штатном промпте).
2. Невалидный JSON в ответе → пробрасывает `json.JSONDecodeError`.
3. Имя канала и поля стиля попадают в текст запроса к LLM.

### Test cases
- **возвращает 10 идей**: LLM-ответ `{"ideas": [10 строк]}` → список длины 10
- **значения совпадают**: возвращённый список == `payload["ideas"]`
- **невалидный JSON**: ответ `"not json {{{"` → `json.JSONDecodeError`
- **данные в промпте**: `create()` вызван с content, содержащим `channel_name` и значения полей стиля

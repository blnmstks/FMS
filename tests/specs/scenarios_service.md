# Spec: `app/services/scenarios.generate_scenario`

## Signature
```python
def generate_scenario(
    idea_name: str,
    channel_name: str,
    channel_description: str,
    channel_style: dict,
    transcript_texts: list[str],
) -> str
```

## Contract

Генерирует подробный сценарий видео по выбранной идее в стиле канала через LLM.
Сценарий обязан содержать сильный сторителлинг и драматизм и соблюдать правила:
matches Style DNA, pacing/rhythm, emotional flow, hits target word count, no generic
structures.

### Inputs
| Param | Type | Описание |
|-------|------|----------|
| `idea_name` | str | заголовок выбранной идеи (raw_idea) |
| `channel_name` | str | имя канала |
| `channel_description` | str | описание канала |
| `channel_style` | dict | поля стиля (как минимум ключи из `SCENARIO_STYLE_FIELDS`) |
| `transcript_texts` | list[str] | содержимое файлов транскриптов (Style DNA) |

Собирает user-content из `GENERATE_SCENARIO_PROMPT` + заголовок идеи + имя/описание канала
+ 13 полей стиля (`SCENARIO_STYLE_FIELDS` — все `STYLE_FIELDS` кроме `average_word_count`)
+ тексты транскриптов.

Вызывает `get_client().chat.completions.create(model=DEFAULT_MODEL, messages=[system, user])`
**без `response_format`** (чистый текст). System-сообщение запрещает любые
преамбулы/комментарии/markdown — только сценарий.

Печатает usage (строка `[LLM usage] ...` как в `ideas`).

### Output
Возвращает `response.choices[0].message.content.strip()` — строку сценария, и ничего больше.

### `SCENARIO_STYLE_FIELDS`
`niche`, `target_audience`, `hook_style`, `script_flow`, `sentence_rhythm`, `tone`,
`transitions`, `curiosity_gaps`, `emotional_triggers`, `retention_techniques`,
`direct_address`, `words_per_second`, `target_word_count`.

### Invariants
1. Возвращает ровно тот текст, что прислал LLM (после `.strip()`), без обёрток.
2. LLM вызывается **без** `response_format` (ответ — plain text, не JSON).
3. Заголовок идеи, поля стиля и тексты транскриптов попадают в текст запроса к LLM.

### Test cases
- **возвращает текст сценария**: LLM-ответ `"  SCENARIO TEXT  "` → `"SCENARIO TEXT"`
- **без response_format**: `create()` вызван без ключа `response_format`
- **данные в промпте**: `create()` вызван с content, содержащим `idea_name`, значение поля
  стиля (`niche`) и текст транскрипта

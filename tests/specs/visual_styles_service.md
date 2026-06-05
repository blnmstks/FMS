# Spec: `app/services/visual_styles.generate_visual_style`

## Signature
```python
def generate_visual_style(
    idea_name: str,
    scenario: str,
    channel_style: dict,
    image_paths: list[str],
) -> dict
```

## Contract

По приложенным изображениям (визуальный референс), идее, сценарию и Style DNA канала через
LLM (vision) извлекает визуальный стиль клипов и Character Reference Sheet.

### Inputs
| Param | Type | Описание |
|-------|------|----------|
| `idea_name` | str | заголовок идеи (`scenario_finished`) |
| `scenario` | str | текст сценария (по нему определяются повторяющиеся персонажи и их число) |
| `channel_style` | dict | поля Style DNA (как минимум ключи `VISUAL_STYLE_INPUT_FIELDS`) |
| `image_paths` | list[str] | пути к изображениям-референсам (рекомендуется 5, принимаем сколько дали) |

Кодирует изображения через `encode_images(image_paths)` ([app/utils/images.py](../../app/utils/images.py)).
User-content = текстовый блок (`GENERATE_VISUAL_STYLE_PROMPT` + idea_name + сценарий +
строки Style DNA) **плюс** блоки изображений. System-сообщение — «You are a JSON API…».
Вызывает `create(model=DEFAULT_MODEL, messages=[system, user], response_format={"type":"json_object"})`.
Печатает usage. Парсит `json.JSONDecoder().raw_decode(...)`.

### `VISUAL_STYLE_INPUT_FIELDS`
`niche`, `target_audience`, `hook_style`, `script_flow`, `sentence_rhythm`, `tone`,
`transitions`, `curiosity_gaps`, `emotional_triggers`, `retention_techniques`,
`direct_address`, `words_per_second`, `average_word_count`
(отличается от scenario-набора: есть `average_word_count`, нет `target_word_count`).

### Output
Возвращает полный распарсенный dict ответа LLM: 7 плоских полей `VISUAL_STYLE_FIELDS`
(`art_style, color_pallet, lighting_style, camera_style, composition, detail_level, mood`)
+ `characters` (Character Reference Sheet). Хранение персонажей — отдельная задача; сервис
их только возвращает.

### Invariants
1. LLM вызывается **с** `response_format={"type":"json_object"}`.
2. В запрос попадают idea_name, текст сценария, значения Style DNA и закодированные изображения.
3. Возвращаемый dict содержит все ключи `VISUAL_STYLE_FIELDS`.

### Test cases
- **парсит JSON в dict**: мок LLM возвращает JSON с 7 полями + `characters` → dict содержит
  все `VISUAL_STYLE_FIELDS` и ключ `characters`
- **response_format задан**: `create()` вызван с `response_format={"type":"json_object"}`
- **изображения и данные в запросе**: `encode_images` вызван с `image_paths`; user-content
  содержит idea_name, текст сценария и значение поля Style DNA

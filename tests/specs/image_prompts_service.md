# Spec: `app/services/image_prompts.generate_image_prompt`

## Signature
```python
def generate_image_prompt(
    scenario: str,
    visual_style: dict,
    characters: list[dict],
) -> dict
```

## Contract

По полному сценарию, Visual Style Profile (поля строки `visual_styles`) и набору персонажей
(`characters_sheet`) через LLM генерирует image-prompt **только для первого бита** сценария.

### Inputs
| Param | Type | Описание |
|-------|------|----------|
| `scenario` | str | текст сценария идеи (`clips_visual_style_finished`) |
| `visual_style` | dict | поля визуального стиля клипов (значения `VISUAL_STYLE_FIELDS`) |
| `characters` | list[dict] | персонажи сценария с их данными (строки `characters_sheet`) |

User-content — единый текстовый блок: `GENERATE_IMAGE_PROMPT_PROMPT` + `Scenario:` + текст
сценария + `Visual Style Profile:` (строки `ключ: значение` по `visual_style`) +
`Characters:` (`json.dumps(characters, ensure_ascii=False, indent=2, default=str)` — у
персонажей `face`/`outfit` приходят как dict из JSONB). System-сообщение — «You are a JSON API…».
Вызывает `create(model=DEFAULT_MODEL, messages=[system, user], response_format={"type":"json_object"})`.
Печатает usage (`prompt_tokens / completion_tokens / total_tokens`). Парсит
`json.JSONDecoder().raw_decode(...)`.

### Output
Возвращает полный распарсенный dict ответа LLM формы
`{ "image_prompt", "camera_angle", "lighting", "mood", "action" }`. Хранение —
отдельная задача (`db.insert_image_prompt`); сервис только возвращает dict.

### Invariants
1. LLM вызывается **с** `response_format={"type":"json_object"}`.
2. В запрос попадают текст сценария, значения `visual_style` и данные персонажей.
3. Изображения не передаются (это текстовый шаг, без vision).

### Test cases
- **парсит JSON в dict**: мок LLM возвращает JSON с 5 полями → dict содержит
  `image_prompt`, `camera_angle`, `lighting`, `mood`, `action`
- **response_format задан**: `create()` вызван с `response_format={"type":"json_object"}`
- **данные в запросе**: user-content содержит текст сценария, значение поля стиля и имя персонажа

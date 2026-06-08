# Spec: `app/services/video_prompts.generate_video_prompts`

## Signature
```python
def generate_video_prompts(
    scenario: str,
    visual_style: dict,
    characters: list[dict],
    beats: list[dict],
) -> dict
```

## Contract

По полному сценарию, Visual Style Profile (поля строки `visual_styles`), набору персонажей
(`characters_sheet`) и **уже существующим битам** сценария через LLM генерирует для **каждого
бита** видео-промпт (`video_prompt`) и описание финального кадра (`end_frame`). Биты заданы извне
(созданы на шаге 9, длительности посчитаны на шаге 11) — сервис их НЕ режет и НЕ выдумывает: один
LLM-проход покрывает все биты сразу, чтобы работала сцепка `end_frame[i] → вход клипа[i+1]`.

### Inputs
| Param | Type | Описание |
|-------|------|----------|
| `scenario` | str | текст сценария идеи (`audio_beats_generated`) |
| `visual_style` | dict | поля визуального стиля клипов (значения `VISUAL_STYLE_FIELDS`) |
| `characters` | list[dict] | персонажи сценария с их данными (строки `characters_sheet`) |
| `beats` | list[dict] | заданные биты в порядке сценария: `{id, audio_text, duration}` |

User-content — единый текстовый блок: `GENERATE_VIDEO_PROMPTS_PROMPT` + `Scenario:` + текст
сценария + `Visual Style Profile:` (строки `ключ: значение` по `visual_style`) +
`Characters:` (`json.dumps(characters, ensure_ascii=False, indent=2, default=str)` — у
персонажей `face`/`outfit` приходят как dict из JSONB) + `Beats:`
(`json.dumps(beats, ensure_ascii=False, indent=2, default=str)`). System-сообщение —
«You are a JSON API…». Вызывает
`create(model=DEFAULT_MODEL, messages=[system, user], response_format={"type":"json_object"})`.
Печатает usage (`prompt_tokens / completion_tokens / total_tokens`). Парсит
`json.JSONDecoder().raw_decode(response.choices[0].message.content.strip())`.

### Output
Возвращает полный распарсенный dict ответа LLM формы
`{ "beats": [ {id, video_prompt, end_frame} ] }`, где `id` — тот же `audio_beat_prompts.id`,
что был передан во входных битах. Хранение — отдельная задача (`db.replace_video_prompts`);
сервис только возвращает dict.

### Invariants
1. LLM вызывается **с** `response_format={"type":"json_object"}`.
2. В запрос попадают текст сценария, значения `visual_style`, данные персонажей и заданные биты
   (их `id`/`audio_text`).
3. Изображения не передаются (это текстовый шаг, без vision).
4. Невалидный JSON → пробрасывается `json.JSONDecodeError`.

### Test cases
- **парсит JSON в dict**: мок LLM возвращает `{"beats": [...]}` → dict содержит ключ `beats`
- **response_format задан**: `create()` вызван с `response_format={"type":"json_object"}`
- **данные в запросе**: user-content содержит текст сценария, значение поля стиля, имя персонажа
  и `audio_text`/`id` бита
- **битый JSON**: контент не-JSON → `pytest.raises(json.JSONDecodeError)`

# Spec: `app/services/audio_prompts.generate_audio_prompts`

## Signature
```python
def generate_audio_prompts(scenario: str) -> dict
```

## Contract

По полному тексту сценария через LLM генерирует промпты **аудио-сегментов** (для TTS) и их
**битов** (шаг 9 конвейера). Ответ ожидается строго JSON.

### Inputs
| Param | Type | Описание |
|-------|------|----------|
| `scenario` | str | текст сценария идеи (статус `image_generated`) |

User-content — единый текстовый блок: `GENERATE_AUDIO_PROMPTS_PROMPT` + `\n\nScenario:\n` + текст
сценария. System-сообщение — «You are a JSON API. Respond only with valid JSON, no markdown, no
commentary.». Вызывает
`create(model=DEFAULT_MODEL, messages=[system, user], response_format={"type":"json_object"})`.
Печатает usage (`prompt_tokens / completion_tokens / total_tokens`). Парсит
`json.JSONDecoder().raw_decode(response.choices[0].message.content.strip())`.

### Output
Возвращает полный распарсенный dict ответа LLM формы
`{ "audio_segments": [ {seg_id, speaker, emotion, tts_text, beat_ids} ], "beats": [ {id, seg_id, audio_text} ] }`.
Хранение — отдельная задача (`db.replace_audio_prompts`); сервис только возвращает dict.

### Invariants
1. LLM вызывается **с** `response_format={"type":"json_object"}`.
2. В user-content попадает текст сценария.
3. Возвращается распарсенный dict как есть (оба массива `audio_segments` и `beats`).
4. Невалидный JSON → пробрасывается `json.JSONDecodeError`.

### Test cases
- **парсит JSON в dict**: мок LLM возвращает payload с `audio_segments` + `beats` → dict содержит
  оба ключа
- **response_format задан**: `create()` вызван с `response_format={"type":"json_object"}`
- **сценарий в запросе**: user-content содержит текст сценария
- **битый JSON**: контент не-JSON → `pytest.raises(json.JSONDecodeError)`

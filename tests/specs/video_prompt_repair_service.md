# Spec: `app/services/video_prompt_repair`

Self-repair шага 13. Когда все сид-попытки бита забракованы QC-гейтом, причина отказа уходит
обратно в LLM, чтобы починить сам промпт (а не перебирать сиды дальше). Текстовый LLM-вызов
(без картинок: вердикт QC уже описывает проблему словами — дёшево).

## `repair_video_prompt(video_prompt: str, end_frame: str, qc_verdict: dict) -> dict`

### Contract
1. `get_client()`; user-content — единый текстовый блок: `REPAIR_VIDEO_PROMPT_PROMPT` +
   `Current video_prompt:` + текущий `video_prompt` + `Current end_frame:` + текущий `end_frame`
   + `QC verdict (why the clip was rejected):` + `json.dumps(qc_verdict, ...)` (весь вердикт —
   `reason` и флаги `face_visible_in_final_frame`/`same_character_as_reference`/`severe_artifacts`).
2. System — «You are a JSON API…»; `create(model=DEFAULT_MODEL, messages=[system, user],
   response_format={"type":"json_object"})`.
3. Парс `json.JSONDecoder().raw_decode(response.choices[0].message.content.strip())`; печать usage
   и `reason`; возврат dict.

### Invariants
1. `response_format={"type":"json_object"}`, модель — `DEFAULT_MODEL`.
2. В запрос попадают текущие `video_prompt`, `end_frame` и причина отказа (`qc_verdict["reason"]`).
   Инструкция `REPAIR_VIDEO_PROMPT_PROMPT` несёт те же ограничения LTX-2, что и шаблон v8:
   никакого читаемого текста/мелкой графики, одно простое действие, плавное движение, без
   диалогов/звука (ia2v) — чтобы self-repair не «чинил» в сторону текста/каши. Плюс continuity-
   правила (v9, зеркало `GENERATE_VIDEO_PROMPTS_PROMPT`): движение описывается как начинающееся из
   покоя, НЕ как уже завершённое; реквизит не «материализуется» в руке и не задаётся метафорой;
   `end_frame` фиксирует положение рук/реквизита/позы, а не только лицо — чтобы починка одного бита
   не вносила скачок на стыке заново. (QC-гейт видит только 3 кадра одного клипа и шов между битами
   не детектит — непрерывность держится промптом.)
3. Возвращается распарсенный dict ответа (ожидается `{video_prompt, end_frame}`); интерпретация и
   запись в БД — задача вызывающего узла (`update_video_beat_prompt`).
4. Невалидный JSON ответа — `json.JSONDecodeError` наверх (не глотается).
5. Без vision — content всегда строка (картинки не передаются).

### Test cases (unit; `get_client` замокан, ответ — фикстура `mock_llm_response`)
- **JSON-формат**: `create()` вызван с `response_format={"type":"json_object"}`, модель —
  `DEFAULT_MODEL`.
- **данные в запросе**: user-content (строка) содержит текущий `video_prompt`, `end_frame` и
  текст причины из `qc_verdict["reason"]`.
- **возврат**: dict ответа пробрасывается как есть (`{"video_prompt": ..., "end_frame": ...}`).
- **кривой JSON**: контент не-JSON → `pytest.raises(json.JSONDecodeError)`.

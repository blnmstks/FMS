# Spec: `app/services/audio_tts`

Бизнес-логика шага 10: по строке `audio_seg_prompts` выбирает голос спикера, формирует текст для
TTS, синтезирует речь и сохраняет WAV.

**Передача эмоций в TTS временно отключена** (по запросу): `emotion` из сегмента в синтез не
передаётся, структурированный промпт (SCENE / DIRECTOR'S NOTES / теги) убран. Колонка `emotion`
в БД и её генерация на шаге 9 сохранены — это точка повторного включения.

## `resolve_voice(speaker: str) -> str`

### Contract
`SPEAKER_VOICE_MAP.get(speaker, DEFAULT_TTS_VOICE)` — стабильное соответствие имени спикера
пресетному голосу Gemini; неизвестный/`None` спикер → `DEFAULT_TTS_VOICE`. Pure.

### Test cases
- **спикер в карте**: `resolve_voice("Narrator") == SPEAKER_VOICE_MAP["Narrator"]`
- **неизвестный спикер**: `resolve_voice("__nope__") == DEFAULT_TTS_VOICE`

## `build_tts_prompt(segment: dict) -> str`

### Contract
Возвращает текст, который уходит в TTS за один проход — **ровно `segment["tts_text"]`**
(`segment.get("tts_text") or ""`). Эмоция и спикер в передачу не вмешиваются. Отсутствующий
`tts_text` → `""`. Pure. Тонкий сид — точка повторного включения эмоций позже.

### Test cases
- **дословно**: для `segment={"tts_text": "Welcome back, everyone.", "emotion": "calm", ...}`
  результат `== "Welcome back, everyone."` (без эмоции/спикера)
- **нет текста**: `build_tts_prompt({}) == ""`

## `generate_segment_audio(segment: dict, idea_id: int) -> str`

### Contract
Оркестрация одного сегмента: `resolve_voice(segment["speaker"])` → `build_tts_prompt(segment)`
→ `google_tts_client.synthesize(prompt, voice, GEMINI_TTS_MODEL)` →
`utils.audio.write_wav(pcm, <AUDIO_DIR>/idea-<idea_id>-seg-<seg_id>-<ts>.wav)`. Возвращает путь.

### Invariants
1. `synthesize` вызывается с голосом из `resolve_voice` и моделью `GEMINI_TTS_MODEL`.
2. Имя файла содержит `idea-<idea_id>-seg-<seg_id>` и лежит под `AUDIO_DIR`, расширение `.wav`.
3. Возвращает путь, который вернул `write_wav`.

### Test cases (unit, `synthesize`/`write_wav` замоканы)
- **синтез и сохранение**: для `segment={"seg_id":11,"speaker":"Host",...}`, `idea_id=7`
  `synthesize` вызван с `resolve_voice("Host")` и `GEMINI_TTS_MODEL`; `write_wav` получил PCM от
  `synthesize` и путь под `AUDIO_DIR` с `idea-7-seg-11`; функция вернула путь от `write_wav`

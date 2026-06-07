# Spec: `app/infrastructure/google_tts_client`

Только транспорт к Google Gemini TTS через SDK `google-genai`. Без бизнес-логики: сборка
промпта, выбор голоса и сохранение файла живут в сервисе. API-ключ берётся из
`app.config.GOOGLE_API_KEY`.

## `get_client() -> genai.Client`

### Contract
Возвращает `genai.Client(api_key=GOOGLE_API_KEY)`. Аналог `llm_client.get_client` — только
настройка подключения, без побочных эффектов.

## `synthesize(prompt: str, voice_name: str, model: str) -> bytes`

### Contract
Один проход TTS (single-speaker). Вызывает
`client.models.generate_content(model=model, contents=prompt, config=GenerateContentConfig(
response_modalities=["AUDIO"], speech_config=SpeechConfig(voice_config=VoiceConfig(
prebuilt_voice_config=PrebuiltVoiceConfig(voice_name=voice_name)))))` и возвращает сырые
PCM-байты `response.candidates[0].content.parts[0].inline_data.data` (PCM signed 16-bit LE,
24000 Hz, mono).

### Invariants
1. `model` и `contents` передаются как есть (`contents == prompt`).
2. `config.response_modalities == ["AUDIO"]`.
3. `config.speech_config.voice_config.prebuilt_voice_config.voice_name == voice_name`
   (single-speaker — ровно один голос на вызов).
4. Возвращает байты из `inline_data.data` без преобразований (обёртка в WAV — задача утилиты).

### Test cases (unit, клиент замокан через `get_client`)
- **синтез**: `synthesize("PROMPT", "Charon", "gemini-3.1-flash-tts-preview")` дергает
  `generate_content` с `model`/`contents`, конфиг содержит `response_modalities=["AUDIO"]` и
  `voice_name == "Charon"`; возвращает `b"PCMDATA"` из мок-ответа.

import json

from app.config import DEFAULT_MODEL
from app.infrastructure.llm_client import get_client, log_llm_input
from app.prompts.audio_prompts import GENERATE_AUDIO_PROMPTS_PROMPT


def generate_audio_prompts(scenario: str) -> dict:
    # По сценарию через ИИ генерирует промпты аудио-сегментов (для TTS) и их битов. Ответ строго JSON.
    # Возвращает распарсенный dict {"audio_segments": [...], "beats": [...]}.
    # Хранение — отдельная задача (db.replace_audio_prompts); сервис только возвращает dict.
    client = get_client()
    user_content = f"{GENERATE_AUDIO_PROMPTS_PROMPT}\n\nScenario:\n{scenario}"

    messages = [
        {
            "role": "system",
            "content": "You are a JSON API. Respond only with valid JSON, no markdown, no commentary.",
        },
        {"role": "user", "content": user_content},
    ]
    log_llm_input(messages)
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )

    usage = response.usage
    print(
        f"\n[LLM usage] input: {usage.prompt_tokens} tokens | "
        f"output: {usage.completion_tokens} tokens | "
        f"total: {usage.total_tokens} tokens"
    )

    data, _ = json.JSONDecoder().raw_decode(response.choices[0].message.content.strip())
    return data

import json

from app.config import DEFAULT_MODEL
from app.db import STYLE_FIELDS
from app.infrastructure.llm_client import get_client, log_llm_input
from app.prompts.transcripts import ANALYZE_TRANSCRIPTS_PROMPT


def analyze_transcripts(texts: list[str]) -> dict:
    # Анализирует список текстов транскриптов через ИИ и возвращает dict с полями стилистики для channel_info.
    # Все транскрипты объединяются в один запрос; JSON-ответ LLM парсится в {field: value}.
    client = get_client()
    combined = "\n\n---\n\n".join(texts)
    messages = [
        {
            "role": "system",
            "content": "You are a JSON API. Respond only with valid JSON, no markdown, no commentary.",
        },
        {
            "role": "user",
            "content": f"{ANALYZE_TRANSCRIPTS_PROMPT}\n\nTranscripts:\n{combined}",
        },
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
    return {field: data[field] for field in STYLE_FIELDS}

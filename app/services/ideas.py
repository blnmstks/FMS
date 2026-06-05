import json

from app.config import DEFAULT_MODEL
from app.infrastructure.llm_client import get_client
from app.prompts.ideas import GENERATE_VIDEO_IDEAS_PROMPT

# Поля стиля, передаваемые в LLM для генерации идей (все STYLE_FIELDS кроме average_word_count).
IDEA_STYLE_FIELDS = [
    "niche",
    "target_audience",
    "hook_style",
    "script_flow",
    "sentence_rhythm",
    "tone",
    "transitions",
    "curiosity_gaps",
    "emotional_triggers",
    "retention_techniques",
    "direct_address",
    "words_per_second",
    "target_word_count",
]


def generate_video_ideas(
    channel_name: str,
    channel_description: str,
    channel_style: dict,
    transcript_texts: list[str],
) -> list[str]:
    # Генерирует список видео-идей в стиле канала через ИИ.
    # В запрос передаются имя и описание канала, поля стиля (IDEA_STYLE_FIELDS) и тексты транскриптов.
    # JSON-ответ LLM ожидается в виде {"ideas": [...]}; возвращается список идей.
    client = get_client()
    style_lines = "\n".join(
        f"{field}: {channel_style.get(field, '')}" for field in IDEA_STYLE_FIELDS
    )
    transcripts = "\n\n---\n\n".join(transcript_texts)
    user_content = (
        f"{GENERATE_VIDEO_IDEAS_PROMPT}\n\n"
        f"Channel name: {channel_name}\n"
        f"Channel description: {channel_description}\n\n"
        f"Channel style:\n{style_lines}\n\n"
        f"Past transcripts:\n{transcripts}"
    )
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a JSON API. Respond only with valid JSON, no markdown, no commentary.",
            },
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
    )

    usage = response.usage
    print(
        f"\n[LLM usage] input: {usage.prompt_tokens} tokens | "
        f"output: {usage.completion_tokens} tokens | "
        f"total: {usage.total_tokens} tokens"
    )

    data, _ = json.JSONDecoder().raw_decode(response.choices[0].message.content.strip())
    return data["ideas"]

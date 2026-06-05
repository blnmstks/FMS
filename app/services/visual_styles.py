import json

from app.config import DEFAULT_MODEL
from app.infrastructure.llm_client import get_client, log_llm_input
from app.prompts.visual_styles import GENERATE_VISUAL_STYLE_PROMPT
from app.utils.images import encode_images

# Поля Style DNA, передаваемые в LLM для анализа визуального стиля (по ТЗ шага 6):
# есть average_word_count, нет target_word_count — отличается от scenario/idea-наборов.
VISUAL_STYLE_INPUT_FIELDS = [
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
    "average_word_count",
]


def generate_visual_style(
    idea_name: str,
    scenario: str,
    channel_style: dict,
    image_paths: list[str],
) -> dict:
    # По референс-изображениям + идее + сценарию + Style DNA канала извлекает визуальный стиль
    # клипов и Character Reference Sheet через ИИ (vision). Ответ ожидается строго JSON.
    # Возвращает полный распарсенный dict (7 полей стиля + characters). Хранение персонажей —
    # отдельная задача; сервис их только возвращает.
    client = get_client()
    images = encode_images(image_paths)
    style_lines = "\n".join(
        f"{field}: {channel_style.get(field, '')}" for field in VISUAL_STYLE_INPUT_FIELDS
    )
    text = (
        f"{GENERATE_VISUAL_STYLE_PROMPT}\n\n"
        f"Video idea (title): {idea_name}\n\n"
        f"Scenario (use it to determine recurring characters and their count):\n{scenario}\n\n"
        f"Style DNA:\n{style_lines}"
    )
    content = [{"type": "text", "text": text}] + images

    messages = [
        {
            "role": "system",
            "content": "You are a JSON API. Respond only with valid JSON, no markdown, no commentary.",
        },
        {"role": "user", "content": content},
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

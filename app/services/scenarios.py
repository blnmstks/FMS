from app.config import DEFAULT_MODEL
from app.infrastructure.llm_client import get_client, log_llm_input
from app.prompts.scenarios import GENERATE_SCENARIO_PROMPT

# Поля Style DNA, передаваемые в LLM для генерации сценария
# (все STYLE_FIELDS кроме average_word_count).
SCENARIO_STYLE_FIELDS = [
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


def generate_scenario(
    idea_name: str,
    channel_name: str,
    channel_description: str,
    channel_style: dict,
    transcript_texts: list[str],
) -> str:
    # Генерирует подробный сценарий по выбранной идее в стиле канала через ИИ.
    # Ответ ожидается чистым текстом (без JSON): возвращается только текст сценария.
    client = get_client()
    style_lines = "\n".join(
        f"{field}: {channel_style.get(field, '')}" for field in SCENARIO_STYLE_FIELDS
    )
    transcripts = "\n\n---\n\n".join(transcript_texts)
    user_content = (
        f"{GENERATE_SCENARIO_PROMPT}\n\n"
        f"Video idea (title): {idea_name}\n"
        f"Channel name: {channel_name}\n"
        f"Channel description: {channel_description}\n\n"
        f"Style DNA:\n{style_lines}\n\n"
        f"Past transcripts (reference for voice, pacing and rhythm):\n{transcripts}"
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You output only the final video scenario as plain text — no preamble, "
                "no commentary, no markdown, nothing but the scenario."
            ),
        },
        {"role": "user", "content": user_content},
    ]
    log_llm_input(messages)
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
    )

    usage = response.usage
    print(
        f"\n[LLM usage] input: {usage.prompt_tokens} tokens | "
        f"output: {usage.completion_tokens} tokens | "
        f"total: {usage.total_tokens} tokens"
    )

    return response.choices[0].message.content.strip()

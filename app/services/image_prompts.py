import json

from app.config import DEFAULT_MODEL
from app.infrastructure.llm_client import get_client, log_llm_input
from app.prompts.image_prompts import GENERATE_IMAGE_PROMPT_PROMPT


def generate_image_prompt(
    scenario: str,
    visual_style: dict,
    characters: list[dict],
) -> dict:
    # По сценарию + Visual Style Profile + персонажам генерирует через ИИ image-prompt
    # ТОЛЬКО для первого бита сценария. Ответ ожидается строго JSON.
    # Возвращает распарсенный dict (image_prompt, camera_angle, lighting, mood, action).
    # Хранение — отдельная задача (db.insert_image_prompt); сервис только возвращает dict.
    client = get_client()
    style_lines = "\n".join(f"{k}: {v}" for k, v in visual_style.items())
    characters_text = json.dumps(characters, ensure_ascii=False, indent=2, default=str)
    user_content = (
        f"{GENERATE_IMAGE_PROMPT_PROMPT}\n\n"
        f"Scenario:\n{scenario}\n\n"
        f"Visual Style Profile:\n{style_lines}\n\n"
        f"Characters:\n{characters_text}"
    )

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

import json

from app.config import DEFAULT_MODEL
from app.infrastructure.llm_client import get_client, log_llm_input
from app.prompts.video_prompts import GENERATE_VIDEO_PROMPTS_PROMPT


def generate_video_prompts(
    scenario: str,
    visual_style: dict,
    characters: list[dict],
    beats: list[dict],
) -> dict:
    # По сценарию + Visual Style Profile + персонажам + УЖЕ существующим битам (id, audio_text,
    # duration) генерирует через ИИ video_prompt и end_frame для КАЖДОГО бита. Биты заданы извне
    # (шаги 9/11) — сервис их не режет и не выдумывает; один проход по всем битам ради сцепки
    # end_frame[i] -> вход клипа[i+1]. Ответ ожидается строго JSON.
    # Возвращает распарсенный dict {"beats": [{id, video_prompt, end_frame}]}.
    # Хранение — отдельная задача (db.replace_video_prompts); сервис только возвращает dict.
    client = get_client()
    style_lines = "\n".join(f"{k}: {v}" for k, v in visual_style.items())
    characters_text = json.dumps(characters, ensure_ascii=False, indent=2, default=str)
    beats_text = json.dumps(beats, ensure_ascii=False, indent=2, default=str)
    user_content = (
        f"{GENERATE_VIDEO_PROMPTS_PROMPT}\n\n"
        f"Scenario:\n{scenario}\n\n"
        f"Visual Style Profile:\n{style_lines}\n\n"
        f"Characters:\n{characters_text}\n\n"
        f"Beats:\n{beats_text}"
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

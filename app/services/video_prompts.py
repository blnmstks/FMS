import json

from app.config import DEFAULT_MODEL
from app.db import IMAGE_PROMPT_FIELDS
from app.infrastructure.llm_client import get_client, log_llm_input
from app.prompts.video_prompts import GENERATE_VIDEO_PROMPTS_PROMPT
from app.utils.images import encode_images


def generate_video_prompts(
    scenario: str,
    visual_style: dict,
    characters: list[dict],
    segments: list[dict],
    first_beat_image_path: str | None = None,
    image_prompt: dict | None = None,
) -> dict:
    # По сценарию + Visual Style Profile + персонажам + УЖЕ существующим СЕГМЕНТАМ (с вложенными
    # битами) генерирует через ИИ video_prompt и end_frame для КАЖДОГО бита. Вход сегмент-
    # группированный (один спикер = один непрерывный визуальный момент), чтобы LLM планировала
    # единую дугу камеры на сегмент. Сегменты/биты заданы извне (шаги 9/11) — сервис их не режет
    # и не выдумывает; один проход по всем битам ради сцепки end_frame[i] -> вход клипа[i+1].
    # first_beat_image_path — РЕАЛЬНАЯ картинка шага 8 (буквальный входной кадр бита 1): уходит
    # в LLM как изображение (vision, паттерн visual_styles), чтобы бит 1 анимировал ровно её, а
    # не пере-ставил сцену (на idea-1 картинка «в машине» + промпт «за столом» дали морф-артефакт).
    # image_prompt — текст шага 7, по которому картинка генерировалась (поля IMAGE_PROMPT_FIELDS).
    # Без картинки — прежний текстовый вызов (обратная совместимость).
    # Ответ строго JSON. Возвращает распарсенный dict {"beats": [{id, video_prompt, end_frame}]}
    # (выход по-битный). Хранение — отдельная задача (db.replace_video_prompts).
    client = get_client()
    style_lines = "\n".join(f"{k}: {v}" for k, v in visual_style.items())
    characters_text = json.dumps(characters, ensure_ascii=False, indent=2, default=str)
    segments_text = json.dumps(segments, ensure_ascii=False, indent=2, default=str)
    user_content = (
        f"{GENERATE_VIDEO_PROMPTS_PROMPT}\n\n"
        f"Scenario:\n{scenario}\n\n"
        f"Visual Style Profile:\n{style_lines}\n\n"
        f"Characters:\n{characters_text}\n\n"
        f"Segments:\n{segments_text}"
    )
    if image_prompt:
        ip_lines = "\n".join(
            f"{f}: {image_prompt[f]}" for f in IMAGE_PROMPT_FIELDS if image_prompt.get(f)
        )
        user_content += (
            "\n\nFirst-beat image prompt (how the attached beat-1 start frame was generated):\n"
            f"{ip_lines}"
        )

    content = user_content
    if first_beat_image_path:
        content = [{"type": "text", "text": user_content}] + encode_images([first_beat_image_path])

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

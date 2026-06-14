import json

from app.config import DEFAULT_MODEL
from app.infrastructure.llm_client import get_client
from app.prompts.video_prompt_repair import REPAIR_VIDEO_PROMPT_PROMPT


def repair_video_prompt(video_prompt: str, end_frame: str, qc_verdict: dict) -> dict:
    # Self-repair шага 13: по текущим video_prompt/end_frame бита и вердикту QC (причина отказа +
    # флаги) LLM переписывает оба поля, устраняя названную поломку. Текстовый вызов (без картинок —
    # дёшево; reason описывает проблему словами). Ответ строго JSON; кривой JSON — исключение
    # наверх (не глотаем). Возвращает {"video_prompt", "end_frame"}; запись в БД — задача узла.
    client = get_client()
    user_content = (
        f"{REPAIR_VIDEO_PROMPT_PROMPT}\n\n"
        f"Current video_prompt:\n{video_prompt}\n\n"
        f"Current end_frame:\n{end_frame}\n\n"
        f"QC verdict (why the clip was rejected):\n"
        f"{json.dumps(qc_verdict, ensure_ascii=False, indent=2, default=str)}"
    )
    messages = [
        {
            "role": "system",
            "content": "You are a JSON API. Respond only with valid JSON, no markdown, no commentary.",
        },
        {"role": "user", "content": user_content},
    ]
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )

    data, _ = json.JSONDecoder().raw_decode(response.choices[0].message.content.strip())
    usage = response.usage
    print(
        f"[repair] reason={qc_verdict.get('reason')!r} | "
        f"tokens in/out: {usage.prompt_tokens}/{usage.completion_tokens}"
    )
    return data

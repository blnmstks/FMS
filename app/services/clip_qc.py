import json
from pathlib import Path

from app.config import DEFAULT_MODEL, VIDEOS_DIR
from app.infrastructure.llm_client import get_client
from app.prompts.clip_qc import CLIP_QC_PROMPT
from app.utils.images import encode_images
from app.utils.video import extract_frame_at, extract_last_frame


def qc_frame_paths(clip_path: str) -> list[str]:
    # Пути трёх QC-кадров клипа (first/mid/last) в VIDEOS_DIR/frames/qc/. Единый источник имён —
    # используется и при извлечении (review_clip), и при уборке зафейленных клипов (узел шага 13).
    stem = Path(clip_path).stem
    qc_dir = Path(VIDEOS_DIR) / "frames" / "qc"
    return [str(qc_dir / f"{stem}-{kind}.png") for kind in ("first", "mid", "last")]


def review_clip(clip_path: str, reference_image_path: str, duration_seconds: float) -> dict:
    # QC-гейт шага 13: vision-LLM смотрит референс персонажа (картинка шага 8) и три кадра клипа
    # (first/mid/last) и выносит вердикт pass/fail. Ловит ровно те поломки, что рушат сцепку
    # по последнему кадру: лицо пропало/закрыто графикой в финальном кадре, персонаж «подменён»,
    # грубые артефакты. Кадры остаются в VIDEOS_DIR/frames/qc/ — инспектируемы при отладке.
    # Ответ строго JSON (как в visual_styles); кривой JSON — исключение наверх (не глотаем).
    stem = Path(clip_path).stem
    first_path, mid_path, last_path = qc_frame_paths(clip_path)
    first = extract_frame_at(clip_path, 0.0, first_path)
    mid = extract_frame_at(clip_path, duration_seconds / 2, mid_path)
    last = extract_last_frame(clip_path, last_path)

    client = get_client()
    # Порядок изображений фиксирован промптом: REFERENCE, FIRST, MID, LAST.
    content = [{"type": "text", "text": CLIP_QC_PROMPT}] + encode_images(
        [reference_image_path, first, mid, last]
    )
    messages = [
        {
            "role": "system",
            "content": "You are a JSON API. Respond only with valid JSON, no markdown, no commentary.",
        },
        {"role": "user", "content": content},
    ]
    # log_llm_input здесь не используется: он печатает messages как есть, а это мегабайты base64.
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )

    data, _ = json.JSONDecoder().raw_decode(response.choices[0].message.content.strip())
    usage = response.usage
    print(
        f"[clip_qc] {stem}: verdict={data.get('verdict')} ({data.get('reason')}) | "
        f"tokens in/out: {usage.prompt_tokens}/{usage.completion_tokens}"
    )
    return data

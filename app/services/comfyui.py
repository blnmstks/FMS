import time
from pathlib import Path
from uuid import uuid4

from app.config import COMFYUI_IMAGE_PROMPT_NODE, COMFYUI_IMAGE_WORKFLOW, IMAGES_DIR
from app.db import IMAGE_PROMPT_FIELDS
from app.infrastructure.comfyui_client import (
    download_image,
    get_history,
    queue_prompt,
    upload_image,
)
from app.utils.workflow import load_workflow, set_node_input

# Дефолт под медленные модели (Flux: загрузка модели + сэмплинг легко дольше 30с).
# Слишком короткий таймаут → TimeoutError до скачивания, и копия в проект не пишется.
DEFAULT_TIMEOUT = 300.0


def generate_image(
    workflow_path: str,
    prompt_text: str,
    prompt_node_id: str,
    output_path: str,
    image_path: str | None = None,
    image_node_id: str | None = None,
    poll_interval: float = 1.0,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    # Загружает workflow в API-format, подставляет промпт по node id, при необходимости
    # заливает входное изображение и подставляет его, отправляет в ComfyUI, ждёт результат
    # (polling /history) и сохраняет первое полученное изображение в output_path.
    workflow = load_workflow(workflow_path)
    set_node_input(workflow, prompt_node_id, "text", prompt_text)

    if image_path:
        name = upload_image(image_path)["name"]
        set_node_input(workflow, image_node_id, "image", name)

    prompt_id = queue_prompt(workflow, uuid4().hex)
    image_info = _wait_for_image(prompt_id, poll_interval, timeout)

    data = download_image(image_info["filename"], image_info["subfolder"], image_info["type"])
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return output_path


def _wait_for_image(prompt_id: str, poll_interval: float, timeout: float) -> dict:
    # Опрашивает /history, пока не появятся outputs, и возвращает первое изображение
    # ({filename, subfolder, type}). По истечении timeout бросает TimeoutError.
    deadline = time.monotonic() + timeout
    while True:
        history = get_history(prompt_id)
        outputs = history.get(prompt_id, {}).get("outputs")
        if outputs:
            for node_output in outputs.values():
                images = node_output.get("images")
                if images:
                    return images[0]
        if time.monotonic() >= deadline:
            raise TimeoutError(f"ComfyUI prompt {prompt_id} did not finish within {timeout}s")
        time.sleep(poll_interval)


def resolve_output_path(out: str | None, workflow_path: str, images_dir: str) -> str:
    # Куда писать копию в проекте: абсолютный out — как есть; относительный — внутрь
    # images_dir; пустой — дефолтное имя "<workflow-stem>-<timestamp>.png" внутри images_dir.
    if out:
        p = Path(out)
        return str(p) if p.is_absolute() else str(Path(images_dir) / p)
    stem = Path(workflow_path).stem
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return str(Path(images_dir) / f"{stem}-{timestamp}.png")


def build_prompt_text(image_prompt: dict) -> str:
    # Объединяет непустые поля сохранённого image-prompt в порядке IMAGE_PROMPT_FIELDS через ", ".
    # Лишние ключи строки БД (id/scenario/created_at) игнорируются.
    parts = [str(image_prompt[f]).strip() for f in IMAGE_PROMPT_FIELDS if image_prompt.get(f)]
    return ", ".join(parts)


def generate_first_beat_image(image_prompt: dict, idea_id: int) -> str:
    # Бизнес-логика шага 8: собирает текст из image-prompt, резолвит путь под IMAGES_DIR и
    # генерирует картинку первого бита через ComfyUI (workflow/node из конфига). Возвращает путь.
    prompt_text = build_prompt_text(image_prompt)
    name = f"idea-{idea_id}-first-beat-{time.strftime('%Y%m%d-%H%M%S')}.png"
    out = resolve_output_path(name, COMFYUI_IMAGE_WORKFLOW, IMAGES_DIR)
    return generate_image(COMFYUI_IMAGE_WORKFLOW, prompt_text, COMFYUI_IMAGE_PROMPT_NODE, out)


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Minimal ComfyUI client")
    parser.add_argument("--workflow", required=True, help="Path to API-format workflow JSON")
    parser.add_argument("--prompt", required=True, help="Prompt text to inject")
    parser.add_argument("--prompt-node", required=True, help="Node id for the prompt text")
    parser.add_argument(
        "--out",
        help=f"Output image path; relative paths go under {IMAGES_DIR} "
        "(default: <workflow>-<timestamp>.png there)",
    )
    parser.add_argument("--image", help="Optional input image to upload")
    parser.add_argument("--image-node", help="Node id for the input image")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, help="Seconds to wait for the result"
    )
    args = parser.parse_args()

    output_path = resolve_output_path(args.out, args.workflow, IMAGES_DIR)
    saved = generate_image(
        workflow_path=args.workflow,
        prompt_text=args.prompt,
        prompt_node_id=args.prompt_node,
        output_path=output_path,
        image_path=args.image,
        image_node_id=args.image_node,
        timeout=args.timeout,
    )
    print(f"Saved: {saved}")


if __name__ == "__main__":
    _main()

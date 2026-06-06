import time
from pathlib import Path
from uuid import uuid4

from app.infrastructure.comfyui_client import (
    download_image,
    get_history,
    queue_prompt,
    upload_image,
)
from app.utils.workflow import load_workflow, set_node_input


def generate_image(
    workflow_path: str,
    prompt_text: str,
    prompt_node_id: str,
    output_path: str,
    image_path: str | None = None,
    image_node_id: str | None = None,
    poll_interval: float = 1.0,
    timeout: float = 30.0,
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


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Minimal ComfyUI client")
    parser.add_argument("--workflow", required=True, help="Path to API-format workflow JSON")
    parser.add_argument("--prompt", required=True, help="Prompt text to inject")
    parser.add_argument("--prompt-node", required=True, help="Node id for the prompt text")
    parser.add_argument("--out", required=True, help="Output image path")
    parser.add_argument("--image", help="Optional input image to upload")
    parser.add_argument("--image-node", help="Node id for the input image")
    args = parser.parse_args()

    saved = generate_image(
        workflow_path=args.workflow,
        prompt_text=args.prompt,
        prompt_node_id=args.prompt_node,
        output_path=args.out,
        image_path=args.image,
        image_node_id=args.image_node,
    )
    print(f"Saved: {saved}")


if __name__ == "__main__":
    _main()

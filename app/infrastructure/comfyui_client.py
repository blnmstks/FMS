from pathlib import Path

import requests

from app.config import COMFYUI_URL


def upload_image(image_path: str) -> dict:
    # Заливает локальный файл в ComfyUI как multipart (поле "image").
    # Возвращает распарсенный JSON {name, subfolder, type}.
    p = Path(image_path)
    with p.open("rb") as f:
        response = requests.post(
            f"{COMFYUI_URL}/upload/image",
            files={"image": (p.name, f)},
        )
    response.raise_for_status()
    return response.json()


def queue_prompt(workflow: dict, client_id: str) -> str:
    # Ставит workflow в очередь на исполнение. Возвращает prompt_id.
    response = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={"prompt": workflow, "client_id": client_id},
    )
    response.raise_for_status()
    return response.json()["prompt_id"]


def get_history(prompt_id: str) -> dict:
    # Возвращает историю исполнения по prompt_id (распарсенный JSON; {} пока не готово).
    response = requests.get(f"{COMFYUI_URL}/history/{prompt_id}")
    response.raise_for_status()
    return response.json()


def download_image(filename: str, subfolder: str, folder_type: str) -> bytes:
    # Скачивает сгенерированное изображение через /view. Возвращает сырые байты.
    response = requests.get(
        f"{COMFYUI_URL}/view",
        params={"filename": filename, "subfolder": subfolder, "type": folder_type},
    )
    response.raise_for_status()
    return response.content

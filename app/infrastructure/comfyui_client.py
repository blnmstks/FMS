from pathlib import Path

import requests

from app.config import COMFYUI_URL


def _upload_input_file(file_path: str) -> dict:
    # Заливает локальный файл в input-каталог ComfyUI как multipart (поле "image" — имя поля
    # эндпоинта, не тип медиа; /upload/image принимает любой файл). {name, subfolder, type}.
    p = Path(file_path)
    with p.open("rb") as f:
        response = requests.post(
            f"{COMFYUI_URL}/upload/image",
            files={"image": (p.name, f)},
        )
    response.raise_for_status()
    return response.json()


def upload_image(image_path: str) -> dict:
    # Заливает изображение в ComfyUI. Возвращает распарсенный JSON {name, subfolder, type}.
    return _upload_input_file(image_path)


def upload_audio(audio_path: str) -> dict:
    # Заливает аудиофайл тем же /upload/image (общий input-upload; LoadAudio берёт файл по имени).
    # Возвращает распарсенный JSON {name, subfolder, type}.
    return _upload_input_file(audio_path)


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

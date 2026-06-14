import secrets
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from app.config import (
    COMFYUI_IMAGE_PROMPT_NODE,
    COMFYUI_IMAGE_WORKFLOW,
    COMFYUI_VIDEO_AUDIO_NODE,
    COMFYUI_VIDEO_DURATION_NODE,
    COMFYUI_VIDEO_FPS,
    COMFYUI_VIDEO_FPS_NODE,
    COMFYUI_VIDEO_IMAGE_NODE,
    COMFYUI_VIDEO_PROMPT_NODE,
    COMFYUI_VIDEO_WORKFLOW,
    IMAGES_DIR,
    VIDEOS_DIR,
)
from app.db import IMAGE_PROMPT_FIELDS
from app.infrastructure.comfyui_client import (
    download_image,
    get_history,
    queue_prompt,
    upload_audio,
    upload_image,
)
from app.prompts.video_prompts import (
    CAMERA_DISCIPLINE_BLOCK,
    FINAL_FRAME_HOLD_SENTENCE,
    STARTING_FRAME_LEAD_SENTENCE,
)
from app.utils.audio import pad_wav_to_duration, wav_duration_seconds
from app.utils.video import ltx_snap_duration, mux_clip_audio
from app.utils.workflow import load_workflow, set_node_input

# Дефолт под медленные модели (Flux: загрузка модели + сэмплинг легко дольше 30с).
# Слишком короткий таймаут → TimeoutError до скачивания, и копия в проект не пишется.
DEFAULT_TIMEOUT = 300.0
# Видео медленнее картинки (LTX-2.3: загрузка + сэмплинг + апскейл).
DEFAULT_VIDEO_TIMEOUT = 1800.0
# Ключи, под которыми ComfyUI кладёт выходные файлы в history (SaveImage→images, SaveVideo→иной).
_OUTPUT_FILE_KEYS = ("images", "gifs", "videos")


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
    image_info = _wait_for_output(prompt_id, poll_interval, timeout)

    data = download_image(image_info["filename"], image_info["subfolder"], image_info["type"])
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return output_path


def _first_output_file(outputs: dict) -> dict | None:
    # Первый выходной файл из outputs нод по любому из _OUTPUT_FILE_KEYS ({filename, subfolder,
    # type}). Нода SaveVideo кладёт результат под ключ, отличный от images. Нет файлов → None.
    for node_output in outputs.values():
        for key in _OUTPUT_FILE_KEYS:
            files = node_output.get(key)
            if files:
                return files[0]
    return None


def _wait_for_output(prompt_id: str, poll_interval: float, timeout: float) -> dict:
    # Опрашивает /history, пока не появится первый выходной файл (image/video), и возвращает его
    # ({filename, subfolder, type}). По истечении timeout бросает TimeoutError.
    deadline = time.monotonic() + timeout
    while True:
        history = get_history(prompt_id)
        outputs = history.get(prompt_id, {}).get("outputs")
        if outputs:
            found = _first_output_file(outputs)
            if found:
                return found
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


def build_video_prompt_text(video_beat_prompt: dict, prev_end_frame: str | None = None) -> str:
    # Для I2V стартовый кадр, финальный кадр и дисциплина камеры — отдельные обязательные
    # инструкции. prev_end_frame (end_frame ПРЕДЫДУЩЕГО бита) — буквальный входной freeze этого
    # клипа (frame 0): блок STARTING FRAME велит LTX начать движение ровно из него (поза/руки/
    # реквизит/мимика), а не «прыгнуть» в готовое состояние — код-уровневый якорь сцепки субъекта
    # (на первом бите prev_end_frame=None — старт это картинка шага 8, блока нет). Финальный кадр
    # станет входом следующего клипа, а камер-блок — код-уровневая гарантия «tripod-first» на каждый
    # клип (стык битов — стоп-кадр: бесшовно сцепляются только статичные состояния), независимая от
    # того, насколько дисциплинированно LLM шага 12 описала камеру. Финальный кадр закрепляется
    # УТВЕРДИТЕЛЬНОЙ hold-фразой; запретительных списков в позитивном промпте нет (видеомодель не
    # понимает отрицаний — токены работали как призыв нарисовать запрещённое).

    starting_frame = str(prev_end_frame or "").strip()
    video_prompt = str(video_beat_prompt.get("video_prompt") or "").strip()
    end_frame = str(video_beat_prompt.get("end_frame") or "").strip()
    parts = []
    if starting_frame:
        parts.append(f"STARTING FRAME\n{STARTING_FRAME_LEAD_SENTENCE}\n{starting_frame}")
    if video_prompt:
        parts.append(f"SHOT ACTION\n{video_prompt}")
    if end_frame:
        parts.append(f"MANDATORY FINAL FRAME\n{end_frame}\n{FINAL_FRAME_HOLD_SENTENCE}")
    if video_prompt:
        parts.append(CAMERA_DISCIPLINE_BLOCK)
    return "\n\n".join(parts)


def _patch_noise_seeds(workflow: dict, beat_id: int, seed: int | None) -> None:
    # Всем нодам RandomNoise — свежие сиды (base+i по нодам в порядке id). Хардкод-сиды из
    # JSON-экспорта не должны доезжать до сервера никогда: одинаковый шум на всех битах давал
    # повторяющиеся артефакты, а ретрай в точности воспроизводил тот же брак. Явный seed —
    # детерминированный повтор; печать — чтобы удачный сид можно было воспроизвести.
    base = seed if seed is not None else secrets.randbits(48)
    noise_nodes = sorted(
        nid for nid, node in workflow.items() if node.get("class_type") == "RandomNoise"
    )
    for i, nid in enumerate(noise_nodes):
        set_node_input(workflow, nid, "noise_seed", base + i)
    seeds = ", ".join(f"{nid}={base + i}" for i, nid in enumerate(noise_nodes))
    print(f"[comfyui] beat {beat_id}: noise seeds {seeds}")


def generate_beat_clip(
    prompt_text: str,
    first_frame_path: str,
    audio_path: str,
    idea_id: int,
    beat_id: int,
    poll_interval: float = 1.0,
    timeout: float = DEFAULT_VIDEO_TIMEOUT,
    seed: int | None = None,
) -> str:
    # Бизнес-логика шага 13: генерирует видео-клип одного бита через ComfyUI (workflow/ноды из
    # конфига). Подаёт промпт, первый кадр (заливка через upload_image) и аудиобит, ПАДДИРОВАННЫЙ
    # тишиной до snap-длительности (кадры LTX = 8n+1, snap только вверх: видео никогда не короче
    # речи, а сырую длину модель молча резала вниз — хвост реплики обрезался бы). После скачивания
    # дорожка клипа заменяется на этот же WAV (выход ComfyUI — голос после Audio-VAE-нейрокодека),
    # заодно срезаются метаданные с полным ComfyUI-графом. Сохраняет под VIDEOS_DIR/clips
    # (расширение — из имени файла ComfyUI, иначе .mp4). Возвращает путь.
    workflow = load_workflow(COMFYUI_VIDEO_WORKFLOW)
    set_node_input(workflow, COMFYUI_VIDEO_PROMPT_NODE, "value", prompt_text)
    # Печатаем финальный positive prompt ровно в том виде, в каком он лёг в prompt-ноду и уйдёт
    # на сервер — чтобы наглядно видеть, что собрал build_video_prompt_text на каждый бит.
    print(f"\n[comfyui] beat {beat_id} — POSITIVE PROMPT → node {COMFYUI_VIDEO_PROMPT_NODE}")
    print("-" * 70)
    print(workflow[COMFYUI_VIDEO_PROMPT_NODE]["inputs"]["value"])
    print("-" * 70)

    frame_name = upload_image(first_frame_path)["name"]
    set_node_input(workflow, COMFYUI_VIDEO_IMAGE_NODE, "image", frame_name)

    # fps берём из конфига (гайд LTX-2: 48–60 для плавности) и патчим в ноду Frame Rate; та же
    # частота идёт в snap-математику, чтобы кадры остались валидными (8n+1) и совпали с нодой.
    set_node_input(workflow, COMFYUI_VIDEO_FPS_NODE, "value", COMFYUI_VIDEO_FPS)
    snapped = ltx_snap_duration(wav_duration_seconds(audio_path), COMFYUI_VIDEO_FPS)
    set_node_input(workflow, COMFYUI_VIDEO_DURATION_NODE, "value", snapped)

    _patch_noise_seeds(workflow, beat_id, seed)

    padded_wav = str(Path(tempfile.gettempdir()) / f"fms-beat-{beat_id}-{uuid4().hex}.wav")
    try:
        pad_wav_to_duration(audio_path, padded_wav, snapped)
        audio_name = upload_audio(padded_wav)["name"]
        set_node_input(workflow, COMFYUI_VIDEO_AUDIO_NODE, "audio", audio_name)

        prompt_id = queue_prompt(workflow, uuid4().hex)
        clip_info = _wait_for_output(prompt_id, poll_interval, timeout)

        data = download_image(clip_info["filename"], clip_info["subfolder"], clip_info["type"])
        ext = Path(clip_info["filename"]).suffix or ".mp4"
        name = f"idea-{idea_id}-beat-{beat_id}-{time.strftime('%Y%m%d-%H%M%S')}{ext}"
        out = Path(VIDEOS_DIR) / "clips" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        mux_clip_audio(str(out), padded_wav)
    finally:
        Path(padded_wav).unlink(missing_ok=True)
    return str(out)


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

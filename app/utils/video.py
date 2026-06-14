import math
import os
import subprocess
from pathlib import Path


def ltx_snap_duration(seconds: float, fps: int = 24) -> float:
    # LTX-2.3 генерирует ровно 8n+1 кадров; workflow считает кадры как duration*fps+1, а
    # невалидные значения модель молча режет ВНИЗ (4.6с → 4.375с — риск обрезать хвост речи).
    # Округляем ВВЕРХ до ближайшей валидной длительности: snap >= seconds, кадров 8n+1,
    # видео никогда не короче аудио. Минимум один 8-кадровый блок.
    blocks = max(math.ceil(seconds * fps / 8), 1)
    return blocks * 8 / fps


def extract_last_frame(video_path: str, output_path: str) -> str:
    # Извлекает последний кадр видео в output_path (PNG) через ffmpeg, создавая родительскую папку.
    # -sseof -0.1 — позиция за 0.1с до конца (самый последний кадр); -update 1 — один файл, не
    # последовательность; -q:v 1 — максимальное качество; -y — перезаписать без вопроса.
    # Шаг 13: последний кадр клипа = первый кадр следующего (сцепка мини-клипов без скачков).
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-sseof", "-0.1", "-i", video_path, "-update", "1", "-q:v", "1", str(out)],
        check=True,
        capture_output=True,
    )
    return output_path


def extract_frame_at(video_path: str, seconds: float, output_path: str) -> str:
    # Извлекает один кадр на позиции seconds (PNG), создавая родительскую папку. -ss ДО -i —
    # точный seek по входу; -frames:v 1 — ровно один кадр; -q:v 1 — максимальное качество.
    # Нужна QC-гейту шага 13: кадры first/mid клипа для vision-проверки.
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(seconds),
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "1",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def mux_clip_audio(video_path: str, wav_path: str) -> str:
    # Заменяет аудиодорожку клипа на оригинальный WAV и срезает метаданные — на месте (tmp-файл +
    # атомарный os.replace). Зачем: ComfyUI отдаёт голос после прогона через Audio-VAE (нейрокодек
    # туда-обратно деградирует TTS), а в метаданные SaveVideo кладёт ПОЛНЫЙ ComfyUI-граф (tag
    # prompt) — утечка workflow в публикуемом файле. Видео не перекодируется (-c:v copy); аудио
    # может быть короче видео (snap-паддинг делает их равными) — -shortest не используется.
    tmp = str(Path(video_path).with_suffix(".tmp.mp4"))
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-i",
            wav_path,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-map_metadata",
            "-1",
            "-movflags",
            "+faststart",
            tmp,
        ],
        check=True,
        capture_output=True,
    )
    os.replace(tmp, video_path)
    return video_path

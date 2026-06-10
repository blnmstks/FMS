import subprocess
from pathlib import Path


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

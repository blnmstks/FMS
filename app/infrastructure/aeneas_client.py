import json
import os
import tempfile


def align(wav_path: str, fragments: list[str]) -> list[tuple[float, float]]:
    # Транспорт к forced-alignment движку aeneas: выравнивает известный текст по аудио и возвращает
    # [(begin_sec, end_sec), ...] для каждого непустого фрагмента (в порядке fragments). Логика как
    # в референсном slice_segment.py.
    # Импорт aeneas — ленивый (внутри функции), а не на уровне модуля: aeneas — тяжёлая нативная
    # зависимость (espeak + ffmpeg + сборка C), и её отсутствие не должно ломать сбор юнит-тестов.
    from aeneas.executetask import ExecuteTask
    from aeneas.task import Task

    config = "task_language=eng|is_text_type=plain|os_task_file_format=json"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".fragments.txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("\n".join(fragments))
        frag_path = f.name

    try:
        task = Task(config_string=config)
        task.audio_file_path_absolute = os.path.abspath(wav_path)
        task.text_file_path_absolute = os.path.abspath(frag_path)
        ExecuteTask(task).execute()
        out = json.loads(task.sync_map.json_string)
    finally:
        os.unlink(frag_path)

    spans = []
    for fragment in out["fragments"]:
        if fragment["lines"]:  # пропускаем служебные пустые фрагменты aeneas
            spans.append((float(fragment["begin"]), float(fragment["end"])))
    return spans

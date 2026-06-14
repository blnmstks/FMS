import time
from pathlib import Path

from app.config import AUDIO_DIR
from app.infrastructure.aeneas_client import align
from app.utils.audio import slice_wav, wav_duration_ms

# Граница между фразами кладётся в середину паузы; небольшой запас (мс) на стыках, чтобы не
# отрезать свору/атаку фонемы. (Как в референсном slice_segment.py.)
PAD_MS = 40
# Кап тишины на внутреннем краю бита: длинные паузы между битами не тащатся в клипы целиком —
# мёртвый воздух 0.3-0.6 с на краях давал «подвисшие» стоп-кадры при склейке (видео стоит,
# никто не говорит). Узкие паузы (≤ 2·CAP) режутся по середине, как раньше.
MAX_EDGE_SILENCE_MS = 200


def snap_boundaries(spans, total_ms):
    # Стык между битом k и k+1 — в середине зазора, но не дальше MAX_EDGE_SILENCE_MS от речи
    # (у широкой паузы середина выбрасывается). Края клипа = границы файла. Запас PAD_MS внутри.
    cuts = []
    n = len(spans)
    for i, (b, e) in enumerate(spans):
        start = b * 1000 if i > 0 else 0
        end = e * 1000 if i < n - 1 else total_ms
        if i > 0:
            prev_end = spans[i - 1][1] * 1000
            mid = (prev_end + b * 1000) / 2  # середина паузы перед битом i
            # хвост предыдущего и старт текущего — не дальше капа от своей речи
            cuts[-1] = (cuts[-1][0], min(mid, prev_end + MAX_EDGE_SILENCE_MS))
            start = max(mid, b * 1000 - MAX_EDGE_SILENCE_MS)
        cuts.append(
            (
                max(0, start - PAD_MS if i > 0 else 0),
                min(total_ms, end + PAD_MS if i < n - 1 else total_ms),
            )
        )
    return cuts


def slice_segment_beats(
    seg_audio_path: str, voiced_beats: list[dict], idea_id: int, seg_id: int
) -> list[dict]:
    # Бизнес-логика шага 11 для одного сегмента: выравнивает тексты битов по аудио, считает границы
    # нарезки и режет WAV на по-битовые клипы в AUDIO_DIR/beats. Возвращает манифест
    # [{"beat_id", "path", "duration"}]; в БД не пишет (регистрацию делает узел графа).
    # voiced_beats — только озвученные биты сегмента, уже в нужном порядке.
    fragments = [b["audio_text"] for b in voiced_beats]
    spans = align(seg_audio_path, fragments)
    total_ms = wav_duration_ms(seg_audio_path)
    cuts = snap_boundaries(spans, total_ms)

    ts = time.strftime("%Y%m%d-%H%M%S")
    manifest = []
    for beat, (start_ms, end_ms) in zip(voiced_beats, cuts):
        beat_id = beat["id"]
        name = f"idea-{idea_id}-seg-{seg_id}-beat-{beat_id}-{ts}.wav"
        out_path = str(Path(AUDIO_DIR) / "beats" / name)
        slice_wav(seg_audio_path, out_path, start_ms, end_ms)
        duration = round((end_ms - start_ms) / 1000, 3)
        manifest.append({"beat_id": beat_id, "path": out_path, "duration": duration})
    return manifest

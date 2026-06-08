# Spec: `app/services/audio_beats`

Бизнес-логика шага 11: нарезка одного синтезированного аудио-сегмента (WAV) на отдельные биты по
тексту битов через forced alignment. Собирает infra (`aeneas_client.align`) + utils
(`audio.wav_duration_ms`, `audio.slice_wav`). В БД не пишет — возвращает манифест (узел графа
регистрирует биты через `insert_audio_beat`). Логика портирована из референсного `slice_segment.py`.

`PAD_MS = 40` — небольшой запас (мс) на стыках, чтобы не отрезать атаку/хвост фонемы.

## `snap_boundaries(spans, total_ms) -> list[tuple[float, float]]`

### Contract
Чистая функция. По спанам `[(begin_sec, end_sec), ...]` (выход `align`, в секундах) и полной длине
файла `total_ms` (мс) считает границы нарезки в миллисекундах:
- стык между битом `k` и `k+1` кладётся в **середину паузы** между ними (хвост `k` и старт `k+1`
  совпадают на `mid`);
- старт первого бита — `0`, конец последнего — `total_ms` (края клипа = границы файла);
- к внутренним краям добавляется запас `PAD_MS` (`start-PAD`, `end+PAD`), с клампом в `[0, total_ms]`.

### Invariants
1. Длина результата равна длине `spans`.
2. `cuts[0][0] == 0` и `cuts[-1][1] == total_ms`.
3. Для соседних битов конец предыдущего = середина паузы, старт следующего = `mid - PAD_MS`.
4. Один спан → один кат `(0, total_ms)` (целый файл).

### Test cases (unit, pure)
- **один бит**: `snap_boundaries([(0.5, 2.0)], 3000) == [(0, 3000)]`
- **два бита**: для `spans=[(0.0,1.0),(1.5,2.5)]`, `total_ms=3000` → `mid = (1000+1500)/2 = 1250`;
  `cuts[0] == (0, 1250)`, `cuts[1] == (1250 - 40, 3000)`; `cuts[0][0] == 0`, `cuts[-1][1] == 3000`

## `slice_segment_beats(seg_audio_path, voiced_beats, idea_id, seg_id) -> list[dict]`

### Contract
Оркестрация одного сегмента. `voiced_beats` — биты сегмента (только озвученные, уже в нужном
порядке), каждый `{"id", "audio_text", ...}`. Шаги:
`fragments = [b["audio_text"] for b in voiced_beats]` → `align(seg_audio_path, fragments)` →
`total_ms = wav_duration_ms(seg_audio_path)` → `cuts = snap_boundaries(spans, total_ms)` → для
каждой пары `(beat, (start_ms, end_ms))`:
`slice_wav(seg_audio_path, <AUDIO_DIR>/beats/idea-<idea_id>-seg-<seg_id>-beat-<beat_id>-<ts>.wav,
start_ms, end_ms)`, `duration = round((end_ms-start_ms)/1000, 3)`.
Возвращает `[{"beat_id": int, "path": str, "duration": float}, ...]`. В БД не пишет.

### Invariants
1. `align` вызывается с `seg_audio_path` и текстами битов в порядке `voiced_beats`.
2. На каждый бит — один `slice_wav` и один элемент манифеста; порядок сохранён.
3. Путь клипа лежит под `AUDIO_DIR/beats` и содержит `idea-<id>-seg-<seg>-beat-<beat>`; ext `.wav`.
4. `duration` — длина ката в секундах (округлённая до мс).
5. `manifest[i]["path"]` равен пути, переданному в `slice_wav` для того же бита.

### Test cases (unit, `align`/`wav_duration_ms`/`slice_wav` замоканы)
- **манифест**: `voiced=[{"id":3,"audio_text":"A"},{"id":4,"audio_text":"B"}]`, `align→[(0,1),(1,2)]`,
  `wav_duration_ms→2000` → 2 элемента; `align` вызван с `("seg.wav", ["A","B"])`; `manifest[0]`
  имеет `beat_id==3`, путь под `AUDIO_DIR/beats` с `idea-7-seg-11-beat-3`, `duration>0`
- **slice_wav на бит**: `slice_wav` вызван 2 раза; первый — с `seg.wav` и тем же путём, что в
  `manifest[0]["path"]`

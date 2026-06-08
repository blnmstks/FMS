# Spec: `app/infrastructure/aeneas_client`

Только транспорт к движку forced alignment [aeneas](https://github.com/readbeyond/aeneas).
Без бизнес-логики: расчёт границ битов, нарезка WAV и запись в БД живут в сервисе/узле.

**Импорт `aeneas` — ленивый, внутри `align`** (а не на уровне модуля, как у `google_tts_client`):
aeneas — тяжёлая нативная зависимость (espeak + ffmpeg + сборка C), и её отсутствие не должно
ломать сбор/прогон юнит-тестов на машинах без неё. Это единственное намеренное отступление от
паттерна infra; в юнит-тестах модули aeneas подменяются через `sys.modules`.

## `align(wav_path: str, fragments: list[str]) -> list[tuple[float, float]]`

### Contract
Выравнивает известный текст по аудио и возвращает `[(begin_sec, end_sec), ...]` для каждого
непустого фрагмента (в порядке `fragments`). Логика как в референсном `slice_segment.py`:
1. Пишет `fragments` (по одному на строку) во временный текстовый файл (UTF-8).
2. Создаёт `Task(config_string="task_language=eng|is_text_type=plain|os_task_file_format=json")`,
   проставляет `audio_file_path_absolute = abspath(wav_path)` и `text_file_path_absolute` на
   временный файл.
3. `ExecuteTask(task).execute()`, парсит `task.sync_map.json_string` (JSON).
4. Возвращает `(float(begin), float(end))` по фрагментам, у которых непустой `lines`
   (служебные пустые фрагменты aeneas пропускаются).
Временный файл удаляется в `finally`.

### Invariants
1. `config_string` содержит `task_language=eng`, `is_text_type=plain`, `os_task_file_format=json`.
2. `audio_file_path_absolute` — абсолютный путь к `wav_path`.
3. Возвращает по одному спану на каждый непустой фрагмент `sync_map`, в исходном порядке.
4. Фрагменты с пустым `lines` отбрасываются.
5. Временный fragments-файл не остаётся на диске (удаляется после выполнения).

### Test cases (unit, модули aeneas подменены через `sys.modules`)
- **парсинг спанов**: при `sync_map` с фрагментами `[{begin:"0.0",end:"1.5",lines:["A"]},
  {begin:"1.5",end:"3.0",lines:["B"]}]` → `align("/x.wav", ["A","B"]) == [(0.0,1.5),(1.5,3.0)]`
- **пустые фрагменты отброшены**: фрагмент с `lines: []` в `sync_map` не попадает в результат
- **конфиг и абсолютный путь**: созданный `Task` получил `config_string` с тремя ключами и
  `audio_file_path_absolute`, оканчивающийся на `x.wav`

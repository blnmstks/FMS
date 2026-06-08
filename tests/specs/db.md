# Spec: `app/db`

## `fetch_channel_info() -> dict`

### Contract
Reads the first row from `channel_info`. No arguments.

| Condition | Returns |
|-----------|---------|
| Row exists AND all 4 fields non-null | `{channel_name, channel_description, channel_avatar, channel_banner, channel_info_complete: True}` |
| No row OR any field is null/empty | `{"channel_info_complete": False}` |

### Invariants
1. Never raises on missing row — returns `{"channel_info_complete": False}`.
2. Returns exactly 5 keys when row found, exactly 1 key when not.

### Test cases
- **row found**: cursor returns `("N", "D", "A", "B")` → full dict with `channel_info_complete=True`
- **no row**: cursor returns `None` → `{"channel_info_complete": False}`
- **partial nulls**: cursor returns `("N", None, "A", "B")` → `{"channel_info_complete": False}`

---

## `upsert_channel_info(data: dict) -> None`

### Contract
Saves channel info. If a row already exists — UPDATE; otherwise — INSERT.

| Condition | SQL executed |
|-----------|-------------|
| `SELECT id` returns a row | `UPDATE channel_info SET ... WHERE id=?` |
| `SELECT id` returns nothing | `INSERT INTO channel_info ...` |

### Invariants
1. Always calls `conn.commit()`.
2. Never raises on valid `data` dict.
3. Does not call both UPDATE and INSERT in the same invocation.

### Test cases
- **existing row**: mock `fetchone()` returns `(1,)` → UPDATE called, INSERT not called
- **new row**: mock `fetchone()` returns `None` → INSERT called, UPDATE not called
- **commit called**: in both cases, `conn.commit()` is called exactly once

---

## `migrate_channel_info_table() -> None`

### Contract
Идемпотентно создаёт **базовую** таблицу `channel_info`, чтобы проект разворачивался на
чистой базе «из коробки». Запускать первой — до `migrate_channel_info_style` (он делает
`ALTER TABLE`) и до `migrate_visual_styles_table` (FK на `channel_info(id)`).

SQL:
```sql
CREATE TABLE IF NOT EXISTS channel_info (
    id SERIAL PRIMARY KEY,
    name TEXT,
    description TEXT,
    avatar TEXT,
    banner TEXT
)
```
Всегда вызывает `conn.commit()`.

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS`) — на существующей базе это no-op, флоу не ломается.
2. Создаёт только базовые колонки (`id, name, description, avatar, banner`); стилевые колонки
   добавляет отдельно `migrate_channel_info_style`.
3. Всегда коммитит.

### Test cases
- **создаёт таблицу**: SQL содержит `CREATE TABLE IF NOT EXISTS channel_info`
- **базовые колонки**: SQL содержит `name`, `description`, `avatar`, `banner`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `migrate_channel_info_style() -> None`

### Contract
Adds 14 new columns to `channel_info` if they do not already exist:
`target_audience`, `hook_style`, `script_flow`, `sentence_rhythm`, `tone`, `transitions`,
`curiosity_gaps`, `emotional_triggers`, `retention_techniques`, `direct_address`,
`words_per_second`, `average_word_count`, `target_word_count`, `transcript_files`.

Uses `ALTER TABLE channel_info ADD COLUMN IF NOT EXISTS <col> TEXT` for each.
Always calls `conn.commit()`.

### Invariants
1. Safe to run multiple times (idempotent — IF NOT EXISTS).
2. Always commits.

---

## `fetch_channel_style_info() -> dict`

### Contract
Reads the style columns from the first row of `channel_info`. No arguments.

| Condition | Returns |
|-----------|---------|
| Row exists AND all 13 style fields non-null/non-empty | Full dict with all 13 keys + `transcript_files` (list) + `channel_style_complete: True` |
| No row OR any of the 13 style fields is null/empty | `{"channel_style_complete": False}` |

### Invariants
1. Never raises on missing row.
2. `transcript_files` is returned as a Python list (parsed from JSON TEXT column); defaults to `[]` if NULL.
3. `channel_style_complete` is `True` only when all 13 style fields are non-null AND non-empty string.

### Test cases
- **all 13 filled**: cursor returns all non-null/non-empty strings → full dict + `channel_style_complete=True`
- **no row**: cursor returns `None` → `{"channel_style_complete": False}`
- **one field null**: cursor returns row with one null → `{"channel_style_complete": False}`
- **one field empty string**: cursor returns row with one `""` → `{"channel_style_complete": False}`
- **transcript_files null**: row exists but `transcript_files` is NULL → `transcript_files=[]` in result

---

## `upsert_channel_style_info(style: dict, obsidian_files: list[str]) -> None`

### Contract
Saves style analysis fields. If a row already exists — UPDATE; otherwise — INSERT.

| Condition | SQL executed |
|-----------|-------------|
| `SELECT id` returns a row | `UPDATE channel_info SET <13 cols + transcript_files> WHERE id=?` |
| `SELECT id` returns nothing | `INSERT INTO channel_info (<13 cols + transcript_files>) VALUES (...)` |

`obsidian_files` is serialized as JSON and stored in `transcript_files`.

### Invariants
1. Always calls `conn.commit()`.
2. Does not call both UPDATE and INSERT in the same invocation.
3. `transcript_files` stored as JSON string.

### Test cases
- **existing row**: mock `fetchone()` returns `(1,)` → UPDATE called, INSERT not called
- **new row**: mock `fetchone()` returns `None` → INSERT called, UPDATE not called
- **commit called**: `conn.commit()` called exactly once in both cases

---

## `migrate_ideas_table() -> None`

### Contract
Создаёт ENUM-тип `idea_status` и таблицу `ideas`, если они ещё не существуют, и
идемпотентно дополняет существующий тип всеми значениями из `IDEAS_STATUSES`
(включая `raw_idea` — самую раннюю стадию жизненного цикла).

SQL, который выполняется:
1. `DO $$ BEGIN CREATE TYPE idea_status AS ENUM (...все значения IDEAS_STATUSES...); EXCEPTION WHEN duplicate_object THEN NULL; END $$` — создаёт тип, если его нет.
2. Для каждого значения из `IDEAS_STATUSES`: `ALTER TYPE idea_status ADD VALUE IF NOT EXISTS '<value>'` — добавляет недостающие значения в уже существующий тип.
3. `CREATE TABLE IF NOT EXISTS ideas (id SERIAL PRIMARY KEY, name TEXT, status idea_status)`

`IDEAS_STATUSES` = `raw_idea`, `scenario_finished`, `clips_visual_style_finished`, `image_prompt_finished`, `image_generated`, `audio_prompts_finished`, `audio_generated`, `audio_beats_generated`, `video_done`.

**Примечание:** значение `audio_beats_generated` (шаг 11 — нарезка сегментов на биты) заняло позицию
прежнего `clips_generated`. `migrate_ideas_table` лишь добавляет новые значения в enum
(`ADD VALUE IF NOT EXISTS`) — старое `clips_generated` остаётся в типе `idea_status` неиспользуемым
(Postgres не удаляет значения enum), на логику не влияет: маппинг шаг↔статус завязан на порядок
Python-списка `IDEAS_STATUSES`, а не на внутренний порядок enum.

Всегда вызывает `conn.commit()`.

### Invariants
1. Безопасно запускать многократно (DO-блок + `ADD VALUE IF NOT EXISTS` + `CREATE TABLE IF NOT EXISTS` — идемпотентна).
2. Существующий тип без новых значений дополняется через `ALTER TYPE ADD VALUE IF NOT EXISTS`.
3. Всегда коммитит.

### Test cases
- **создаёт тип**: `cur.execute` вызывается с SQL содержащим `idea_status` и всеми значениями `IDEAS_STATUSES`
- **дополняет тип**: `cur.execute` вызывается с SQL содержащим `ALTER TYPE idea_status ADD VALUE IF NOT EXISTS`
- **выполняет CREATE TABLE**: `cur.execute` вызывается с SQL содержащим `CREATE TABLE IF NOT EXISTS ideas`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `fetch_idea_by_status(status: str) -> dict`

### Contract
Читает первую идею с заданным `status` из `ideas`: `SELECT id, name FROM ideas WHERE
status = %s LIMIT 1`.

| Condition | Returns |
|-----------|---------|
| Есть строка | `{"idea_id": <id>, "idea_name": <name>, "exists": True}` |
| Строки нет | `{"exists": False}` |

### Test cases
- **строка есть**: cursor возвращает `(7, "X")` → `{"idea_id": 7, "idea_name": "X", "exists": True}`
- **строки нет**: cursor возвращает `None` → `{"exists": False}`

---

## `fetch_raw_idea() -> dict`

### Contract
Тонкая обёртка над `fetch_idea_by_status("raw_idea")` (для совместимости с шагом 5).

| Condition | Returns |
|-----------|---------|
| Есть строка со `status = 'raw_idea'` | `{"idea_id": <id>, "idea_name": <name>, "raw_idea_exists": True}` |
| Строки нет | `{"raw_idea_exists": False}` |

### Invariants
1. Никогда не падает при отсутствии строки — возвращает `{"raw_idea_exists": False}`.
2. Возвращает ровно 3 ключа когда строка найдена, ровно 1 ключ когда нет.

### Test cases
- **строка есть**: cursor возвращает `(7, "My Idea")` → `{"idea_id": 7, "idea_name": "My Idea", "raw_idea_exists": True}`
- **строки нет**: cursor возвращает `None` → `{"raw_idea_exists": False}`

---

## `fetch_present_idea_statuses() -> list[str]`

### Contract
Возвращает список уникальных статусов идей в таблице: `SELECT DISTINCT status FROM ideas`.
Используется диспетчером графа для выбора шага. Пустая таблица → `[]`.

### Test cases
- **есть строки**: cursor `fetchall` → `[("raw_idea",), ("scenario_finished",)]` →
  `["raw_idea", "scenario_finished"]`
- **пусто**: `fetchall` → `[]` → `[]`

---

## `insert_idea(name: str, status: str) -> None`

### Contract
Вставляет новую строку в `ideas`: `INSERT INTO ideas (name, status) VALUES (%s, %s)`.

### Invariants
1. Всегда вызывает `conn.commit()`.
2. Всегда `INSERT` (без проверки существования) — каждая идея новая строка.

### Test cases
- **insert вызван**: `cur.execute` вызывается с SQL содержащим `INSERT INTO ideas`, параметры `(name, status)`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `update_idea_status(idea_id: int, status: str) -> None`

### Contract
Обновляет статус идеи: `UPDATE ideas SET status=%s WHERE id=%s`, параметры `(status, idea_id)`.

### Invariants
1. Всегда вызывает `conn.commit()`.
2. Параметры передаются в порядке `(status, idea_id)`.

### Test cases
- **update вызван**: `cur.execute` вызывается с SQL содержащим `UPDATE ideas`, параметры `(status, idea_id)`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `migrate_scenarios_table() -> None`

### Contract
Создаёт таблицу `scenarios`, если её ещё нет. Безопасно запускать многократно
(`CREATE TABLE IF NOT EXISTS`). FK `idea` ссылается на `ideas(id)` — миграцию `ideas`
нужно выполнять раньше.

SQL:
```sql
CREATE TABLE IF NOT EXISTS scenarios (
    id SERIAL PRIMARY KEY,
    scenario TEXT,
    idea INTEGER REFERENCES ideas(id)
)
```

Всегда вызывает `conn.commit()`.

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS`).
2. Колонка `idea` — внешний ключ на `ideas(id)`.
3. Всегда коммитит.

### Test cases
- **создаёт таблицу**: `cur.execute` вызывается с SQL содержащим `CREATE TABLE IF NOT EXISTS scenarios`
- **FK на ideas**: SQL содержит `REFERENCES ideas`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `insert_scenario(scenario: str, idea_id: int) -> None`

### Contract
Вставляет сгенерированный сценарий, связывая его с идеей:
`INSERT INTO scenarios (scenario, idea) VALUES (%s, %s)`, параметры `(scenario, idea_id)`.

### Invariants
1. Всегда вызывает `conn.commit()`.
2. Всегда `INSERT` — каждый сценарий новая строка.

### Test cases
- **insert вызван**: `cur.execute` вызывается с SQL содержащим `INSERT INTO scenarios`, параметры `(scenario, idea_id)`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## Константы схемы

### `VISUAL_STYLE_FIELDS`
Единственный источник истины для колонок визуального стиля:
`art_style`, `color_pallet`, `lighting_style`, `camera_style`, `composition`,
`detail_level`, `mood`. Используется в `migrate_visual_styles_table` (DDL) и
`upsert_visual_styles` (значения).

### `RELATION_EDGES`
Реестр FK-рёбер графа данных: список кортежей `(child_table, fk_column, parent_table)`,
смысл — `child.<fk_column> -> parent.id`. Единственный источник истины для `fetch_related`.
Текущее содержимое:
- `("visual_styles", "channel_info", "channel_info")`
- `("visual_styles", "idea", "ideas")`
- `("scenarios", "idea", "ideas")`
- `("characters_sheet", "scenario", "scenarios")`
- `("image_prompts", "scenario", "scenarios")`
- `("images", "image_prompt", "image_prompts")`
- `("audio_seg_prompts", "scenario", "scenarios")`
- `("audio_beats", "beat", "audio_beat_prompts")`
- `("video_beat_prompts", "beat", "audio_beat_prompts")`

**Безопасность:** имена таблиц/колонок берутся только из этого whitelist (не из
пользовательского ввода), поэтому их допустимо подставлять в SQL f-строкой.

---

## `migrate_visual_styles_table() -> None`

### Contract
Идемпотентно создаёт таблицу `visual_styles` (визуальный стиль клипов, привязка к идее).
Запускать после `channel_info` (FK `channel_info`) и после `ideas` (FK `idea`).

SQL:
```sql
CREATE TABLE IF NOT EXISTS visual_styles (
    id SERIAL PRIMARY KEY,
    art_style TEXT, color_pallet TEXT, lighting_style TEXT,
    camera_style TEXT, composition TEXT, detail_level TEXT, mood TEXT,
    channel_info INTEGER REFERENCES channel_info(id),
    idea INTEGER REFERENCES ideas(id)
)
```
Плюс идемпотентный апгрейд для уже существующих таблиц:
`ALTER TABLE visual_styles ADD COLUMN IF NOT EXISTS idea INTEGER REFERENCES ideas(id)`.
Колонки стиля генерируются из `VISUAL_STYLE_FIELDS`. Всегда вызывает `conn.commit()`.

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS` + `ADD COLUMN IF NOT EXISTS`).
2. Все колонки из `VISUAL_STYLE_FIELDS` присутствуют в DDL.
3. Колонка `channel_info` — FK на `channel_info(id)`; колонка `idea` — FK на `ideas(id)`.
4. Всегда коммитит.

### Test cases
- **создаёт таблицу**: SQL содержит `CREATE TABLE IF NOT EXISTS visual_styles`
- **все поля**: SQL содержит каждое имя из `VISUAL_STYLE_FIELDS`
- **FK на ideas**: SQL содержит `REFERENCES ideas`
- **idea-колонка**: SQL содержит `idea`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `upsert_visual_styles(style: dict, idea_id: int) -> None`

### Contract
Сохраняет визуальный стиль клипов — **одна строка на идею**. Ключ поиска — колонка
`idea`: `SELECT id FROM visual_styles WHERE idea=%s LIMIT 1`.

| Condition | SQL executed |
|-----------|-------------|
| Строка найдена | `UPDATE visual_styles SET <VISUAL_STYLE_FIELDS, idea> WHERE id=%s` |
| Строки нет | `INSERT INTO visual_styles (<VISUAL_STYLE_FIELDS, idea>) VALUES (...)` |

Значения: `[style[f] for f in VISUAL_STYLE_FIELDS] + [idea_id]`. Колонка `channel_info` не
заполняется (NULL — под будущее brand-уровневое использование). Всегда `conn.commit()`.

### Invariants
1. Всегда вызывает `conn.commit()`.
2. Не вызывает UPDATE и INSERT в одном вызове.
3. Поиск существующей строки идёт по `idea`.

### Test cases
- **существующая строка**: `fetchone()=(1,)` → UPDATE, не INSERT
- **новая строка**: `fetchone()=None` → INSERT, не UPDATE
- **поиск по идее**: SELECT содержит `WHERE idea`, параметр `(idea_id,)`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `fetch_rows(table: str, column: str, value) -> list[dict]`

### Contract
Низкоуровневый помощник: `SELECT * FROM {table} WHERE {column} = %s`. Кортежи строк
маппятся в `dict` по именам колонок из `cursor.description`. Пустой результат → `[]`.

`table`/`column` подставляются f-строкой (идентификаторы нельзя параметризовать) и должны
приходить только из доверенного whitelist (`RELATION_EDGES`); `value` передаётся параметром.

### Invariants
1. Возвращает список `dict` (ключи — имена колонок).
2. Пустой `fetchall()` → `[]`.

### Test cases
- **есть строки**: `description=[("id",),("channel_info",)]`, `fetchall=[(1,"5")]` →
  `[{"id":1,"channel_info":"5"}]`
- **пусто**: `fetchall=[]` → `[]`

---

## `fetch_row_by_id(table: str, value) -> dict | None`

### Contract
`SELECT * FROM {table} WHERE id = %s LIMIT 1`. Возвращает `dict` (по `cursor.description`)
или `None`, если строки нет.

### Invariants
1. Строка есть → `dict` по именам колонок.
2. Строки нет → `None`.

### Test cases
- **строка есть**: `description=[("id",),("name",)]`, `fetchone=(7,"X")` →
  `{"id":7,"name":"X"}`
- **строки нет**: `fetchone=None` → `None`

---

## `fetch_related(source_table: str, source_id: int) -> dict`

### Contract
Обобщённый обход связей источника **в обе стороны** по `RELATION_EDGES`. Возвращает:
```python
{
  "source":   <dict | None>,                      # строка-источник (fetch_row_by_id)
  "parents":  {parent_table: <dict | None>, ...}, # на кого ссылается источник
  "children": {child_table: [<dict>, ...], ...},  # кто ссылается на источник
}
```
Алгоритм по каждому ребру `(child, col, parent)`:
- `parent == source_table` → `children[child] = fetch_rows(child, col, source_id)`;
- `child == source_table` и `source[col]` не `None` →
  `parents[parent] = fetch_row_by_id(parent, source[col])`.

### Invariants
1. `source=None` → `parents`/`children` от рёбер-потомков не заполняются (нет значения FK),
   но «дети» источника-родителя всё равно ищутся по `source_id`.
2. «Дети» — всегда список; «родитель» — `dict` или `None`.

### Test cases
- **источник-родитель** (`channel_info`): `children["visual_styles"]` — список строк
- **источник-потомок** (`scenarios`): `parents["ideas"]` — `dict` строки идеи

---

## `migrate_characters_sheet_table() -> None`

### Contract
Идемпотентно создаёт таблицу `characters_sheet` (персонажи сценария). Запускать после
миграции `scenarios` (FK `scenario`).

SQL:
```sql
CREATE TABLE IF NOT EXISTS characters_sheet (
    id SERIAL PRIMARY KEY,
    name TEXT,
    face JSONB,
    build TEXT,
    outfit JSONB,
    baseline_neutral_expression TEXT,
    scenario INTEGER REFERENCES scenarios(id)
)
```
Всегда вызывает `conn.commit()`.

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS`).
2. `face` и `outfit` — `JSONB`; `scenario` — FK на `scenarios(id)`.
3. Всегда коммитит.

### Test cases
- **создаёт таблицу**: SQL содержит `CREATE TABLE IF NOT EXISTS characters_sheet`
- **JSONB**: SQL содержит `JSONB`
- **FK на scenarios**: SQL содержит `REFERENCES scenarios`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `insert_characters(characters: list[dict], scenario_id: int) -> None`

### Contract
Идемпотентно пересоздаёт набор персонажей сценария: сперва
`DELETE FROM characters_sheet WHERE scenario=%s`, затем на каждый персонаж
`INSERT INTO characters_sheet (name, face, build, outfit, baseline_neutral_expression,
scenario) VALUES (%s,%s,%s,%s,%s,%s)`.

Маппинг из формата LLM (Character Reference Sheet): `name=char.get("label")`,
`face=Jsonb(char.get("face"))`, `build=char.get("build")`,
`outfit=Jsonb(char.get("outfit"))`,
`baseline_neutral_expression=char.get("baseline_neutral_expression")`,
последний параметр — `scenario_id`. Всегда `conn.commit()`.

### Invariants
1. Перед вставкой удаляет существующих персонажей сценария (delete-then-insert).
2. `face`/`outfit` пишутся как JSONB через `Jsonb(...)`.
3. Число INSERT равно числу персонажей; пустой список → только DELETE.
4. Всегда коммитит.

### Test cases
- **delete + insert**: для 2 персонажей — один `DELETE FROM characters_sheet`, два
  `INSERT INTO characters_sheet`; в параметрах первого INSERT `name="Jack"` и последний
  параметр — `scenario_id`
- **пустой список**: только `DELETE`, нет `INSERT`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## Константа `IMAGE_PROMPT_FIELDS`
Единственный источник истины для колонок image-prompt первого бита (таблица `image_prompts`):
`image_prompt`, `camera_angle`, `lighting`, `mood`, `action`. Используется в
`migrate_image_prompts_table` (DDL) и `insert_image_prompt` (значения).

---

## `migrate_image_prompts_table() -> None`

### Contract
Идемпотентно создаёт таблицу `image_prompts` (image-prompt первого бита, привязка к сценарию).
Запускать после миграции `scenarios` (FK `scenario`).

SQL:
```sql
CREATE TABLE IF NOT EXISTS image_prompts (
    id SERIAL PRIMARY KEY,
    image_prompt TEXT, camera_angle TEXT, lighting TEXT, mood TEXT, action TEXT,
    scenario INTEGER REFERENCES scenarios(id)
)
```
Колонки полей генерируются из `IMAGE_PROMPT_FIELDS`. Всегда вызывает `conn.commit()`.

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS`).
2. Все колонки из `IMAGE_PROMPT_FIELDS` присутствуют в DDL.
3. Колонка `scenario` — FK на `scenarios(id)`.
4. Всегда коммитит.

### Test cases
- **создаёт таблицу**: SQL содержит `CREATE TABLE IF NOT EXISTS image_prompts`
- **все поля**: SQL содержит каждое имя из `IMAGE_PROMPT_FIELDS`
- **FK на scenarios**: SQL содержит `REFERENCES scenarios`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `insert_image_prompt(prompt: dict, scenario_id: int) -> None`

### Contract
Вставляет сгенерированный image-prompt первого бита, связывая его со сценарием:
`INSERT INTO image_prompts (<IMAGE_PROMPT_FIELDS>, scenario) VALUES (...)`. Значения:
`[prompt.get(f) for f in IMAGE_PROMPT_FIELDS] + [scenario_id]`. Всегда `conn.commit()`.

### Invariants
1. Всегда вызывает `conn.commit()`.
2. Всегда `INSERT` (без проверки существования) — каждый prompt новая строка.
3. Последний параметр — `scenario_id`.

### Test cases
- **insert вызван**: `cur.execute` вызывается с SQL содержащим `INSERT INTO image_prompts`
- **последний параметр — scenario_id**: параметры INSERT заканчиваются `scenario_id`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `migrate_images_table() -> None`

### Contract
Идемпотентно создаёт таблицу `images` — реестр **сгенерированных** картинок. В БД хранится
не абсолютный путь, а storage-agnostic ключ (`key`) + маркер бэкенда (`storage`), чтобы переезд
на S3 не требовал миграции схемы. Запускать **после** `migrate_image_prompts_table` (FK
`image_prompt` ссылается на `image_prompts(id)`).

SQL:
```sql
CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    storage TEXT NOT NULL DEFAULT 'local',
    key TEXT NOT NULL,
    role TEXT,
    image_prompt INTEGER REFERENCES image_prompts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
```
- `storage` — бэкенд (`local` / в будущем `s3`); DEFAULT — страховка на уровне схемы.
- `key` — относительный ключ файла (напр. `generated/image_prompt/57/01.png`).
- `role` — назначение картинки; пока единственное значение `generated`.
- `created_at` — заполняется БД (DEFAULT `now()`).

Всегда вызывает `conn.commit()`.

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS`).
2. Колонки: `id`, `storage`, `key`, `role`, `image_prompt`, `created_at`.
3. Колонка `image_prompt` — FK на `image_prompts(id)`.
4. Всегда коммитит.

### Test cases
- **создаёт таблицу**: SQL содержит `CREATE TABLE IF NOT EXISTS images`
- **FK на image_prompts**: SQL содержит `REFERENCES image_prompts`
- **колонки**: SQL содержит `storage`, `key`, `role`, `image_prompt`, `created_at`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `insert_image(storage: str, key: str, role: str, image_prompt_id: int) -> None`

### Contract
Регистрирует сгенерированную картинку, связывая её с image-prompt:
`INSERT INTO images (storage, key, role, image_prompt) VALUES (%s,%s,%s,%s)`. Значения:
`(storage, key, role, image_prompt_id)`. Колонка `created_at` не передаётся — её заполняет БД
(DEFAULT `now()`). Всегда `conn.commit()`.

Все аргументы явные, без дефолтов: знание «storage=local, role=generated» — бизнес-логика
будущего сервиса, а не слоя БД (db.py = SQL only).

### Invariants
1. Всегда вызывает `conn.commit()`.
2. Всегда `INSERT` (без проверки существования) — каждая картинка новая строка.
3. Параметры в порядке `(storage, key, role, image_prompt_id)`; последний — `image_prompt_id`.

### Test cases
- **insert вызван**: `cur.execute` вызывается с SQL содержащим `INSERT INTO images`
- **параметры**: параметры INSERT == `(storage, key, role, image_prompt_id)`, последний —
  `image_prompt_id`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `migrate_audio_seg_prompts_table() -> None`

### Contract
Идемпотентно создаёт таблицу `audio_seg_prompts` — аудио-сегменты для TTS, привязанные к
сценарию (что произносится, кем, с какой эмоцией и к каким битам сценария относится сегмент).
Запускать **после** `migrate_scenarios_table` (FK `scenario` ссылается на `scenarios(id)`).

SQL:
```sql
CREATE TABLE IF NOT EXISTS audio_seg_prompts (
    seg_id SERIAL PRIMARY KEY,
    speaker VARCHAR,
    emotion TEXT,
    tts_text TEXT,
    beat_ids INTEGER[],
    scenario INTEGER REFERENCES scenarios(id)
)
```
- `seg_id` — первичный ключ `SERIAL` (та же семантика, что `id` в остальных таблицах, только
  имя другое).
- `speaker` — кто говорит (`VARCHAR`).
- `emotion` — эмоциональная окраска реплики (`TEXT`).
- `tts_text` — текст, который озвучивается (`TEXT`).
- `beat_ids` — массив целых (`INTEGER[]`): к каким битам сценария относится сегмент.
- `scenario` — FK на `scenarios(id)`.

Всегда вызывает `conn.commit()`.

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS`).
2. `seg_id` — `SERIAL PRIMARY KEY`.
3. `beat_ids` — `INTEGER[]`.
4. Колонка `scenario` — внешний ключ на `scenarios(id)`.
5. Всегда коммитит.

### Test cases
- **создаёт таблицу**: SQL содержит `CREATE TABLE IF NOT EXISTS audio_seg_prompts`
- **PK seg_id**: SQL содержит `seg_id SERIAL PRIMARY KEY`
- **массив битов**: SQL содержит `beat_ids INTEGER[]`
- **FK на scenarios**: SQL содержит `REFERENCES scenarios`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `migrate_audio_beat_prompts_table() -> None`

### Contract
Идемпотентно создаёт таблицу `audio_beat_prompts` — биты озвучки сегмента (текст каждого бита
и ссылка на аудио-сегмент). Запускать **после** `migrate_audio_seg_prompts_table` (FK `seg_id`
ссылается на `audio_seg_prompts(seg_id)`).

SQL:
```sql
CREATE TABLE IF NOT EXISTS audio_beat_prompts (
    id SERIAL PRIMARY KEY,
    seg_id INTEGER REFERENCES audio_seg_prompts(seg_id),
    audio_text TEXT
)
```
- `id` — первичный ключ `SERIAL`.
- `seg_id` — FK на `audio_seg_prompts(seg_id)`. Ключ родителя называется `seg_id` (не `id`),
  поэтому ссылка указывает колонку явно.
- `audio_text` — текст бита озвучки (`TEXT`).

Всегда вызывает `conn.commit()`.

**Примечание:** таблица намеренно НЕ входит в `RELATION_EDGES` — реестр и хелперы
`fetch_related`/`fetch_row_by_id` завязаны на PK с именем `id`, а у родителя `audio_seg_prompts`
ключ называется `seg_id`. Обобщение хелперов под произвольное имя PK — отдельная задача.

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS`).
2. `id` — `SERIAL PRIMARY KEY`.
3. Колонка `seg_id` — внешний ключ на `audio_seg_prompts(seg_id)`.
4. Всегда коммитит.

### Test cases
- **создаёт таблицу**: SQL содержит `CREATE TABLE IF NOT EXISTS audio_beat_prompts`
- **PK id**: SQL содержит `id SERIAL PRIMARY KEY`
- **FK на audio_seg_prompts**: SQL содержит `REFERENCES audio_seg_prompts(seg_id)`
- **колонки**: SQL содержит `id`, `seg_id`, `audio_text`

---

## `replace_audio_prompts(segments: list[dict], beats: list[dict], scenario_id: int) -> None`

### Contract
Идемпотентно пересоздаёт промпты аудио-сегментов и их битов для одного сценария (шаг 9).
Формат `segments`/`beats` — из ответа LLM:
- `segments[]`: `{seg_id (локальный), speaker, emotion, tts_text, beat_ids: [int]}`
- `beats[]`: `{id (локальный), seg_id (локальный или null), audio_text}`

Порядок в одной транзакции:
1. `DELETE FROM audio_beat_prompts WHERE seg_id IN (SELECT seg_id FROM audio_seg_prompts WHERE scenario=%s)`
   — биты удаляются первыми (FK на сегменты).
2. `DELETE FROM audio_seg_prompts WHERE scenario=%s`.
3. На каждый сегмент: `INSERT INTO audio_seg_prompts (speaker, emotion, tts_text, beat_ids, scenario)
   VALUES (...) RETURNING seg_id` — локальный `seg_id` → БД-serial `seg_id` (карта `seg_id_map`).
   `beat_ids` пишется как Python-list в `INTEGER[]`.
4. На каждый бит: `INSERT INTO audio_beat_prompts (seg_id, audio_text) VALUES (%s, %s)` — `seg_id`
   берётся из карты по локальному `beat.seg_id`; силентный бит (`seg_id is None`) → `NULL`,
   `audio_text` по умолчанию `""`.

Один `conn.commit()` на всю операцию (атомарность: при ошибке — откат, прежние данные целы).

### Invariants
1. Сначала удаляются биты, затем сегменты (порядок из-за FK), затем вставка.
2. Локальный `seg_id` сегмента маппится на БД-serial через `RETURNING`; биты ссылаются на
   замапленный seg_id.
3. Силентный бит (`seg_id=None`) пишется с `NULL`.
4. Ровно один `conn.commit()`.
5. Пустые списки → только удаление (очистка промптов сценария).

### Test cases
- **порядок delete**: один `DELETE FROM audio_beat_prompts`, один `DELETE FROM audio_seg_prompts`
- **insert сегментов с RETURNING**: на каждый сегмент `INSERT INTO audio_seg_prompts` … `RETURNING seg_id`
- **маппинг seg_id у битов**: при `fetchone.side_effect=[(101,),(102,)]` бит с локальным `seg_id=1`
  вставляется с `seg_id=101`, бит с локальным `seg_id=2` — с `102`; силентный (`seg_id=None`) — с `None`
- **commit один раз**: `conn.commit()` вызывается ровно один раз
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `migrate_audio_table() -> None`

### Contract
Идемпотентно создаёт таблицу `audio` — реестр **сгенерированных** аудио-сегментов (по образцу
`images`: storage-agnostic ключ `key` + маркер бэкенда `storage`, чтобы переезд на S3 не требовал
миграции схемы). Запускать **после** `migrate_audio_seg_prompts_table` (FK `seg_id` ссылается на
`audio_seg_prompts(seg_id)`).

SQL:
```sql
CREATE TABLE IF NOT EXISTS audio (
    id SERIAL PRIMARY KEY,
    storage TEXT NOT NULL DEFAULT 'local',
    key TEXT NOT NULL,
    role TEXT,
    seg_id INTEGER REFERENCES audio_seg_prompts(seg_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
```
- `storage` — бэкенд (`local` / в будущем `s3`); DEFAULT — страховка на уровне схемы.
- `key` — относительный ключ файла (напр. `idea-7-seg-11-20260607-120000.wav`).
- `role` — назначение записи; пока единственное значение `segment`.
- `created_at` — заполняется БД (DEFAULT `now()`).

Всегда вызывает `conn.commit()`.

**Примечание:** таблица намеренно НЕ входит в `RELATION_EDGES` — родитель `audio_seg_prompts`
имеет PK с именем `seg_id` (не `id`), а хелперы `fetch_related`/`fetch_row_by_id` завязаны на
PK `id`. Для чтения использовать `fetch_rows("audio", "seg_id", seg_id)`.

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS`).
2. Колонки: `id`, `storage`, `key`, `role`, `seg_id`, `created_at`.
3. Колонка `seg_id` — FK на `audio_seg_prompts(seg_id)`.
4. Всегда коммитит.

### Test cases
- **создаёт таблицу**: SQL содержит `CREATE TABLE IF NOT EXISTS audio`
- **FK на audio_seg_prompts**: SQL содержит `REFERENCES audio_seg_prompts(seg_id)`
- **колонки**: SQL содержит `storage`, `key`, `role`, `seg_id`, `created_at`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `insert_audio(storage: str, key: str, role: str, seg_id: int) -> None`

### Contract
Регистрирует сгенерированный аудио-сегмент, связывая его с `audio_seg_prompts`:
`INSERT INTO audio (storage, key, role, seg_id) VALUES (%s,%s,%s,%s)`. Значения:
`(storage, key, role, seg_id)`. Колонка `created_at` не передаётся — её заполняет БД
(DEFAULT `now()`). Всегда `conn.commit()`.

Все аргументы явные, без дефолтов: знание «storage=local, role=segment» — бизнес-логика
сервиса/узла, а не слоя БД.

### Invariants
1. Всегда вызывает `conn.commit()`.
2. Всегда `INSERT` (без проверки существования) — каждый сегмент новая строка.
3. Параметры в порядке `(storage, key, role, seg_id)`; последний — `seg_id`.

### Test cases
- **insert вызван**: `cur.execute` вызывается с SQL содержащим `INSERT INTO audio`
- **параметры**: параметры INSERT == `(storage, key, role, seg_id)`, последний — `seg_id`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `migrate_audio_beats_table() -> None`

### Contract
Идемпотентно создаёт таблицу `audio_beats` — реестр **нарезанных** аудиобитов (шаг 11), по образцу
`audio`/`images`: storage-agnostic ключ `key` + маркер бэкенда `storage`. Дополнительно хранит
`duration` — реальную длину бита в секундах (уходит в видео-пайплайн). Запускать **после**
`migrate_audio_beat_prompts_table` (FK `beat` ссылается на `audio_beat_prompts(id)`).

SQL:
```sql
CREATE TABLE IF NOT EXISTS audio_beats (
    id SERIAL PRIMARY KEY,
    storage TEXT NOT NULL DEFAULT 'local',
    key TEXT NOT NULL,
    role TEXT,
    duration DOUBLE PRECISION,
    beat INTEGER REFERENCES audio_beat_prompts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
```
- `key` — относительный ключ файла (напр. `beats/idea-7-seg-11-beat-3-20260607-120000.wav`).
- `role` — назначение записи; пока единственное значение `beat`.
- `duration` — реальная длительность бита в секундах (округлённая).
- `created_at` — заполняется БД (DEFAULT `now()`).

Всегда вызывает `conn.commit()`.

**Примечание:** в отличие от `audio`, таблица входит в `RELATION_EDGES`
(`("audio_beats", "beat", "audio_beat_prompts")`) — родитель `audio_beat_prompts` имеет PK `id`,
поэтому `fetch_related`/`fetch_row_by_id` работают корректно (как для пары `images` ↔ `image_prompts`).

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS`).
2. Колонки: `id`, `storage`, `key`, `role`, `duration`, `beat`, `created_at`.
3. Колонка `beat` — FK на `audio_beat_prompts(id)`.
4. Всегда коммитит.

### Test cases
- **создаёт таблицу**: SQL содержит `CREATE TABLE IF NOT EXISTS audio_beats`
- **FK на audio_beat_prompts**: SQL содержит `REFERENCES audio_beat_prompts(id)`
- **колонки**: SQL содержит `storage`, `key`, `role`, `duration`, `beat`, `created_at`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `insert_audio_beat(storage: str, key: str, role: str, duration: float, beat_id: int) -> None`

### Contract
Регистрирует нарезанный аудиобит, связывая его с `audio_beat_prompts`:
`INSERT INTO audio_beats (storage, key, role, duration, beat) VALUES (%s,%s,%s,%s,%s)`. Значения:
`(storage, key, role, duration, beat_id)`. Колонка `created_at` не передаётся — её заполняет БД
(DEFAULT `now()`). Всегда `conn.commit()`.

Все аргументы явные, без дефолтов: знание «storage=local, role=beat» — бизнес-логика узла, не слоя БД.

### Invariants
1. Всегда вызывает `conn.commit()`.
2. Всегда `INSERT` (без проверки существования) — каждый бит новая строка.
3. Параметры в порядке `(storage, key, role, duration, beat_id)`; последний — `beat_id`.

### Test cases
- **insert вызван**: `cur.execute` вызывается с SQL содержащим `INSERT INTO audio_beats`
- **параметры**: параметры INSERT == `(storage, key, role, duration, beat_id)`, последний — `beat_id`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `delete_audio_beats_for_beats(beat_ids: list[int]) -> None`

### Contract
Удаляет строки `audio_beats`, относящиеся к переданным битам:
`DELETE FROM audio_beats WHERE beat = ANY(%s)` с параметром `(beat_ids,)`. Нужна для чистого
повторного прохода частично нарезанного сегмента (идемпотентность без дублей). Всегда `conn.commit()`.
Пустой список `beat_ids` — корректный no-op на уровне SQL (`= ANY('{}')` не совпадает ни с чем).

### Invariants
1. Всегда вызывает `conn.commit()`.
2. SQL — `DELETE FROM audio_beats WHERE beat = ANY(%s)`, параметр `(beat_ids,)`.

### Test cases
- **delete вызван**: `cur.execute` вызывается с SQL содержащим `DELETE FROM audio_beats`
- **параметр**: параметр == `([1, 2, 3],)`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## Константа `VIDEO_PROMPT_FIELDS`
Единственный источник истины для колонок видео-промпта бита (таблица `video_beat_prompts`):
`video_prompt`, `end_frame`. Используется в `migrate_video_beat_prompts_table` (DDL — косвенно,
через перечисление колонок) и в сервисе/узле как набор полей ответа LLM.

---

## `migrate_video_beat_prompts_table() -> None`

### Contract
Идемпотентно создаёт таблицу `video_beat_prompts` — видео-промпт и финальный кадр **на каждый
бит** (шаг 12). По образцу `audio_beats` ссылается на `audio_beat_prompts(id)`. Запускать
**после** `migrate_audio_beat_prompts_table` (FK `beat` ссылается на `audio_beat_prompts(id)`).

SQL:
```sql
CREATE TABLE IF NOT EXISTS video_beat_prompts (
    id SERIAL PRIMARY KEY,
    beat INTEGER REFERENCES audio_beat_prompts(id),
    video_prompt TEXT,
    end_frame TEXT
)
```
- `id` — первичный ключ `SERIAL`.
- `beat` — FK на `audio_beat_prompts(id)`.
- `video_prompt` — самодостаточное описание клипа бита (`TEXT`).
- `end_frame` — описание финального кадра, вход для следующего клипа (`TEXT`).

Всегда вызывает `conn.commit()`.

**Примечание:** таблица входит в `RELATION_EDGES`
(`("video_beat_prompts", "beat", "audio_beat_prompts")`) — родитель `audio_beat_prompts` имеет PK
`id`, поэтому `fetch_related`/`fetch_rows` работают корректно (как пара `audio_beats` ↔
`audio_beat_prompts`).

### Invariants
1. Идемпотентна (`CREATE TABLE IF NOT EXISTS`).
2. Колонки: `id`, `beat`, `video_prompt`, `end_frame`.
3. Колонка `beat` — FK на `audio_beat_prompts(id)`.
4. Всегда коммитит.

### Test cases
- **создаёт таблицу**: SQL содержит `CREATE TABLE IF NOT EXISTS video_beat_prompts`
- **FK на audio_beat_prompts**: SQL содержит `REFERENCES audio_beat_prompts(id)`
- **колонки**: SQL содержит `video_prompt`, `end_frame`, `beat`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

---

## `replace_video_prompts(beats: list[dict], scenario_id: int) -> None`

### Contract
Идемпотентно пересоздаёт видео-промпты битов одного сценария (шаг 12). Формат `beats` — из ответа
LLM: `{id (= существующий audio_beat_prompts.id), video_prompt, end_frame}`.

Порядок в одной транзакции:
1. `DELETE FROM video_beat_prompts WHERE beat IN (SELECT id FROM audio_beat_prompts WHERE seg_id
   IN (SELECT seg_id FROM audio_seg_prompts WHERE scenario=%s))` — удаляет прежние строки только
   для битов этого сценария.
2. На каждый бит: `INSERT INTO video_beat_prompts (beat, video_prompt, end_frame) VALUES (%s,%s,%s)`
   с параметрами `(beat.get("id"), beat.get("video_prompt"), beat.get("end_frame"))`.

Один `conn.commit()` на всю операцию (атомарность: при ошибке — откат, прежние данные целы).

### Invariants
1. Сначала один `DELETE` (по битам сценария), затем по `INSERT` на каждый бит.
2. `beat` каждого INSERT — `beat["id"]` (существующий `audio_beat_prompts.id`).
3. Ровно один `conn.commit()`.
4. Пустой список → только удаление (очистка видео-промптов сценария).

### Test cases
- **порядок**: один `DELETE FROM video_beat_prompts`, затем по `INSERT INTO video_beat_prompts`
  на каждый бит
- **параметры insert**: на бит `{"id":1,"video_prompt":"vp","end_frame":"ef"}` — INSERT с
  `(1, "vp", "ef")`
- **пустой список**: только `DELETE`, нет `INSERT`
- **commit один раз**: `conn.commit()` вызывается ровно один раз


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

`IDEAS_STATUSES` = `raw_idea`, `scenario_finished`, `clips_visual_style_finished`, `image_prompt_finished`, `image_generated`, `av_prompts_finished`, `audio_generated`, `clips_generated`, `video_done`.

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


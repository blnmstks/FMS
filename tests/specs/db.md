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

`IDEAS_STATUSES` = `raw_idea`, `scenario_finished`, `clips_visual_style_finished`, `image_prompt_finished`, `av_prompts_finished`, `audio_generated`, `clips_generated`, `video_done`.

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

## `fetch_raw_idea() -> dict`

### Contract
Читает первую идею со статусом `raw_idea` из таблицы `ideas`. Аргументов нет.

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

## `insert_idea(name: str, status: str) -> None`

### Contract
Вставляет новую строку в `ideas`: `INSERT INTO ideas (name, status) VALUES (%s, %s)`.

### Invariants
1. Всегда вызывает `conn.commit()`.
2. Всегда `INSERT` (без проверки существования) — каждая идея новая строка.

### Test cases
- **insert вызван**: `cur.execute` вызывается с SQL содержащим `INSERT INTO ideas`, параметры `(name, status)`
- **commit вызван**: `conn.commit()` вызывается ровно один раз

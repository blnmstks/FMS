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

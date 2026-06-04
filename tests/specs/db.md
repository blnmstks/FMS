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

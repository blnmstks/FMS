# Spec: `app/services/branding.analyze_channel`

## Signature
```python
def analyze_channel(channel_name: str, screenshot_paths: list[str]) -> dict
```

## Contract

### Inputs
| Param | Type | Constraints |
|-------|------|-------------|
| `channel_name` | str | non-empty |
| `screenshot_paths` | list[str] | ≥1 valid file paths to images |

### Output
Returns a `dict` with **exactly** these keys:

| Key | Type | Source |
|-----|------|--------|
| `channel_name` | str | one item from `brief["channel_name_variants"]` |
| `channel_description` | str | one item from `brief["channel_description_variants"]` |
| `channel_avatar` | str | `brief["channel_avatar_prompt"]` |
| `channel_banner` | str | `brief["channel_banner_prompt"]` |
| `channel_info_complete` | bool | always `True` |

### Invariants
1. Output always contains all 5 keys — no extras, no missing.
2. `channel_info_complete` is always `True`.
3. Values are drawn from LLM response, not invented.
4. If LLM returns invalid JSON → `json.JSONDecodeError` propagates up (no silent fallback).
5. If LLM returns JSON missing required keys → `KeyError` propagates up.

## Test cases
- **happy path**: valid LLM response → all 5 keys present, `channel_info_complete=True`
- **determinism**: with `random.seed(0)`, selected variant is predictable
- **invalid JSON**: LLM returns `"not json"` → `json.JSONDecodeError` raised
- **missing key**: LLM returns `{}` → `KeyError` raised

# Spec: `app/services/transcripts.analyze_transcripts`

## Signature
```python
def analyze_transcripts(texts: list[str]) -> dict
```

## Contract

### Inputs
| Param | Type | Constraints |
|-------|------|-------------|
| `texts` | list[str] | ≥1 non-empty strings (transcript contents) |

### Output
Returns a `dict` with **exactly** these 13 keys:

| Key | Type |
|-----|------|
| `target_audience` | str |
| `hook_style` | str |
| `script_flow` | str |
| `sentence_rhythm` | str |
| `tone` | str |
| `transitions` | str |
| `curiosity_gaps` | str |
| `emotional_triggers` | str |
| `retention_techniques` | str |
| `direct_address` | str |
| `words_per_second` | str |
| `average_word_count` | str |
| `target_word_count` | str |

### Invariants
1. Output always contains all 13 keys — no extras, no missing.
2. Values are drawn from LLM response, not invented.
3. If LLM returns invalid JSON → `json.JSONDecodeError` propagates up (no silent fallback).
4. If LLM returns JSON missing a required key → `KeyError` propagates up.
5. All transcript texts are concatenated and sent in a single LLM call.

## Test cases
- **happy path**: mocked LLM returns valid JSON with all 13 keys → dict returned as-is
- **invalid JSON**: LLM returns `"not json"` → `json.JSONDecodeError` raised
- **missing key**: LLM returns `{}` → `KeyError` raised when accessing any of the 13 fields

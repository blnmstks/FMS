# Spec: `app/graph` — Step 5 (scenario entry)

## `s5_scenario(state) -> dict`

### Contract
Шаг 5 — точка входа в работу над сценарием. Берёт идею со статусом `raw_idea`
напрямую из БД (источник истины), а не из переданного state.

Вызывает `fetch_raw_idea()`:
- **нет `raw_idea`** (`raw_idea_exists` == False) → печатает в консоль
  `there is no idea for scenario` и возвращает `{"raw_idea_exists": False}`
  (роутер `_route_s5` уведёт обратно на шаг 4).
- **`raw_idea` найдена** → печатает `STATE 5 — working with raw idea: <name>`
  и возвращает `{"idea_id", "idea_name", "raw_idea_exists": True}`.

Генерация самого сценария — будущая часть шага 5 (ветка «идея найдена» пока заглушка).

## `_route_s5(state) -> str`

### Contract
Маршрутизатор после шага 5:
- нет `raw_idea` (`raw_idea_exists` falsy или отсутствует) → `"s4"` (назад к выбору идеи);
- `raw_idea_exists` == True → `END` (завершение графа).

Шаг 4 на любой ветке создаёт `raw_idea`, поэтому цикл `s5 → s4 → (s4_pick →) s5`
завершается за один проход.

### Invariants
1. `s5_scenario` читает идею из БД, не полагаясь на `idea_name`/`idea_id` из state.
2. Отсутствие `raw_idea` → ровно строка `there is no idea for scenario` в консоль
   и возврат на шаг 4.
3. При наличии идеи возвращаемые `idea_id`/`idea_name` соответствуют записи из БД.

### Test cases
- **нет идеи → возврат на s4**: `_route_s5({"raw_idea_exists": False})` == `"s4"`
- **флаг отсутствует → возврат на s4**: `_route_s5({})` == `"s4"`
- **есть идея → END**: `_route_s5({"raw_idea_exists": True})` == `END`
- **узел без идеи**: `fetch_raw_idea` → `{"raw_idea_exists": False}` ⇒ возврат
  `{"raw_idea_exists": False}`, в stdout `there is no idea for scenario`
- **узел с идеей**: `fetch_raw_idea` → `{"idea_id": 7, "idea_name": "X", "raw_idea_exists": True}`
  ⇒ возврат содержит `idea_id == 7`, `idea_name == "X"`, `raw_idea_exists == True`

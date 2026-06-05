# Spec: `app/graph` — диспетчер шагов 5+ по статусам идей

Начиная с шага 5, маршрут определяется статусами идей в таблице `ideas`. Соответствие
статус → шаг линейное (из `IDEAS_STATUSES`): `raw_idea→5`, `scenario_finished→6`,
`clips_visual_style_finished→7`, `image_prompt_finished→8`, `av_prompts_finished→9`,
`audio_generated→10`, `clips_generated→11`, `video_done→12`.

## `STEP_BY_STATUS`
Словарь `{status: 5 + index}` из `IDEAS_STATUSES` (единственный источник истины — порядок
статусов). `FIRST_STEP = 5`.

## `select_target_step(present_statuses: set[str], current_step: int) -> int`

### Contract
Чистая функция выбора целевого шага. `steps` = множество шагов присутствующих статусов.
- нет идей (`steps` пусто) → `4` (создать `raw_idea`);
- `current_step` среди `steps` → `current_step` (свой статус);
- иначе есть предшествующие (`< current_step`) → `min(earlier)` (самый ранний предыдущий);
- иначе → `min(later)` (ближайший последующий).

### Test cases
- свой: `({"raw_idea"}, 5) == 5`; `({"scenario_finished"}, 6) == 6`
- свой приоритетнее: `({"raw_idea", "audio_generated"}, 5) == 5`
- самый ранний предыдущий: `({"scenario_finished", "clips_visual_style_finished"}, 9) == 6`
- предыдущий, когда своего нет: `({"raw_idea"}, 8) == 5`
- только последующие: `({"audio_generated"}, 5) == 10`
- нет идей: `(set(), 5) == 4`

## `dispatch(state) -> dict`

### Contract
Узел-диспетчер: читает статусы из БД (`fetch_present_idea_statuses()`), берёт курсор
`current = state.get("pipeline_step", FIRST_STEP)` и возвращает
`{"pipeline_target": select_target_step(set(present), current)}`.

### Test cases
- `fetch_present_idea_statuses → ["raw_idea"]`, `state={}` → `pipeline_target == 5`
- `fetch_present_idea_statuses → ["scenario_finished"]`, `state={"pipeline_step": 6}` → `6`
- `fetch_present_idea_statuses → []` → `pipeline_target == 4`

## `_route_dispatch(state) -> str`

### Contract
Роутер после диспетчера с защитой от зацикливания:
- `target == 4` → `"s4"`;
- `target` уже в `executed_steps` → `END` (шаг выполнялся за этот прогон; стаб не двигает
  статус — иначе бесконечный цикл);
- иначе → `f"s{target}"`.

### Test cases
- `{"pipeline_target": 5}` → `"s5"`
- `{"pipeline_target": 4}` → `"s4"`
- `{"pipeline_target": 6, "executed_steps": [6]}` → `END`
- `{"pipeline_target": 7, "executed_steps": [5, 6]}` → `"s7"`

## `_advance(state, step, updates=None) -> dict`
Хелпер: помечает `step` выполненным и двигает курсор. Возвращает
`{"pipeline_step": step + 1, "executed_steps": [...прежние, step], **updates}`.

## `s5_scenario(state) -> dict`
Берёт `raw_idea` (диспетчер гарантирует её наличие), генерирует и сохраняет сценарий,
переводит идею в `scenario_finished` (см. ниже), возвращает `_advance(state, 5, {...})`.
Если идеи внезапно нет — защитный `_advance(state, 5)` без работы (диспетчер разрулит).

Ветка «идея найдена»: `fetch_channel_info` + `fetch_channel_style_info` + транскрипты →
`generate_scenario(...)` → `insert_scenario(scenario, idea_id)` →
`update_idea_status(idea_id, "scenario_finished")`.

### Test cases
- идея есть: вызваны `insert_scenario("SCENARIO", 7)` и
  `update_idea_status(7, "scenario_finished")`; результат содержит `pipeline_step == 6` и
  `5 in executed_steps`
- идеи нет: результат содержит `pipeline_step == 6`, `5 in executed_steps`; LLM не вызван

## `s6_visual_style(state) -> dict`
Шаг 6: по идее со статусом `scenario_finished` генерирует визуальный стиль клипов через ИИ
на основе приложенных изображений + сценария + Style DNA канала и сохраняет 7 полей стиля в
`visual_styles` (per-idea upsert), переводит идею в `clips_visual_style_finished`.
Узел самодостаточен (не доверяет state — диспетчер может завести сюда в свежем прогоне).

Ветка «идея найдена»:
- `scenario_text = (fetch_rows("scenarios","idea", idea_id) or [{}])[0].get("scenario","")`;
- `paths_raw = interrupt("STATE 6 — Paste paths to reference images (comma-separated, ~5):")`,
  `paths = [p.strip() for p in paths_raw.split(",") if p.strip()]`;
- `scenario_id` берётся из той же строки (`scenarios[0]["id"]`);
- `style = fetch_channel_style_info()`;
- `profile = generate_visual_style(idea_name, scenario_text, style, paths)`;
- `visual = {f: profile[f] for f in VISUAL_STYLE_FIELDS}`; `upsert_visual_styles(visual, idea_id)`;
- персонажи сохраняются: `insert_characters(profile.get("characters") or [], scenario_id)`
  (если `scenario_id` есть);
- `update_idea_status(idea_id, "clips_visual_style_finished")`;
- `_advance(state, 6, {"idea_id": idea_id, "idea_name": idea_name})`.

Если идеи внезапно нет — защитный `_advance(state, 6)` без работы.

### Test cases
- идея есть (мок `interrupt`→пути, `fetch_rows`→`[{"id":3,"scenario":"SCEN"}]`,
  `fetch_channel_style_info`, `generate_visual_style`→7 полей + characters): вызваны
  `upsert_visual_styles(<7 полей>, idea_id)`,
  `insert_characters(profile["characters"], 3)` и
  `update_idea_status(idea_id, "clips_visual_style_finished")`; `pipeline_step == 7`,
  `6 in executed_steps`
- идеи нет: `pipeline_step == 7`, `6 in executed_steps`; LLM и `insert_characters` не вызваны

## Стабы шагов 7–12 — фабрика `_make_stub(n)`
Возвращает узел `stub(state)`: печатает `STATE {n} — (заглушка) ...` (имя идеи берёт через
`fetch_idea_by_status(IDEAS_STATUSES[n-5])`) и возвращает `_advance(state, n)`.

### Test cases
- `_make_stub(7)(state)` (мок `fetch_idea_by_status`): результат `pipeline_step == 8`,
  `7 in executed_steps`; в stdout `STATE 7`

## Поток графа
```
START → s1 → (s2) → s3 → dispatch
dispatch → _route_dispatch → s4 | s5..s12 | END
s4 → _route_s4 → s4_pick | dispatch
s4_pick → dispatch
s5..s12 → dispatch
```
`_route_s4`: `generated_ideas` есть → `"s4_pick"`, иначе → `"dispatch"`.
`_route_s5` удалён (его роль перешла диспетчеру).

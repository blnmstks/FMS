# Spec: `app/graph` — диспетчер шагов 5+ по статусам идей

Начиная с шага 5, маршрут определяется статусами идей в таблице `ideas`. Соответствие
статус → шаг линейное (из `IDEAS_STATUSES`): `raw_idea→5`, `scenario_finished→6`,
`clips_visual_style_finished→7`, `image_prompt_finished→8`, `image_generated→9`,
`audio_prompts_finished→10`, `audio_generated→11`, `audio_beats_generated→12`, `video_done→13`.

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
- только последующие: `({"audio_generated"}, 5) == 11`
- image_generated → шаг 9: `({"image_generated"}, 8) == 9`
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

## `s7_image_prompt(state) -> dict`
Шаг 7: по идее со статусом `clips_visual_style_finished` генерирует через ИИ image-prompt
**первого бита** сценария и сохраняет его в `image_prompts` (привязка к сценарию), переводит
идею в `image_prompt_finished`. Узел самодостаточен (не доверяет state).

Поток:
- `idea = fetch_idea_by_status("clips_visual_style_finished")`; если `not idea["exists"]` —
  защитный `_advance(state, 7)` без работы (и без `interrupt`);
- `answer = interrupt("STATE 7 — Already have first beat img? (y/n)")`;
- **ветка «yes»** (`answer.strip().lower() in ("y", "yes")`): картинка уже есть — генерации и
  записи в `image_prompts` нет; `update_idea_status(idea_id, "image_generated")` (пропуск шага 8 —
  диспетчер по статусу `image_generated` уводит на шаг 9), `_advance(state, 7, {idea_id, idea_name})`;
- **ветка «no»**:
  - `scenario_row = (fetch_rows("scenarios","idea", idea_id) or [{}])[0]`;
    `scenario_text = scenario_row.get("scenario","")`, `scenario_id = scenario_row.get("id")`;
  - `visual_row = (fetch_rows("visual_styles","idea", idea_id) or [{}])[0]`;
    `visual_style = {f: visual_row.get(f) for f in VISUAL_STYLE_FIELDS}`;
  - `characters = fetch_rows("characters_sheet","scenario", scenario_id)` если `scenario_id`, иначе `[]`;
  - `prompt = generate_image_prompt(scenario_text, visual_style, characters)`;
  - если `scenario_id is not None`: `insert_image_prompt(prompt, scenario_id)`, затем
    `update_idea_status(idea_id, "image_prompt_finished")` (порядок строгий — статус меняется
    ТОЛЬКО после успешного сохранения; при ошибке `insert` исключение пробрасывается, статус и
    курсор не двигаются);
  - `_advance(state, 7, {idea_id, idea_name})`.

`interrupt` стоит ПОСЛЕ guard'а (как в s6): read-операции до него идемпотентны при resume,
а LLM-вызов и запись идут только после ответа.

### Test cases
- «no», идея есть (мок `fetch_idea_by_status`→idea, `interrupt`→"n", `fetch_rows`→строки для
  scenarios/visual_styles/characters, `generate_image_prompt`→5 полей): вызваны
  `insert_image_prompt(prompt, scenario_id)` и
  `update_idea_status(idea_id, "image_prompt_finished")`; `pipeline_step == 8`,
  `7 in executed_steps`
- «yes»: `insert_image_prompt`/`generate_image_prompt` НЕ вызваны; вызван
  `update_idea_status(idea_id, "image_generated")`; `pipeline_step == 8`, `7 in executed_steps`
- идеи нет: `pipeline_step == 8`, `7 in executed_steps`; `interrupt` и `generate_image_prompt`
  не вызваны

## `s8_generate_image(state) -> dict`
Шаг 8: по идее со статусом `image_prompt_finished` генерирует реальное изображение первого
бита через ComfyUI по сохранённому image-prompt, регистрирует картинку в таблице `images` и
переводит идею в `image_generated`. Узел самодостаточен (не доверяет state), полностью
автоматический (без `interrupt`). Статус меняется ТОЛЬКО после успешной генерации и записи —
при ошибке `generate_first_beat_image`/`insert_image` исключение пробрасывается, статус и
курсор не двигаются.

Поток:
- `idea = fetch_idea_by_status("image_prompt_finished")`; если `not idea["exists"]` —
  защитный `_advance(state, 8)` без работы;
- `scenario_row = (fetch_rows("scenarios","idea", idea_id) or [{}])[0]`;
  `scenario_id = scenario_row.get("id")`;
- `image_prompt_row = (fetch_rows("image_prompts","scenario", scenario_id) or [{}])[0]` если
  `scenario_id`, иначе `{}`; `image_prompt_id = image_prompt_row.get("id")`;
- если `image_prompt_id is None` — `_advance(state, 8, {idea_id, idea_name})` без генерации;
- `path = generate_first_beat_image(image_prompt_row, idea_id)` (сервис ComfyUI);
- `insert_image("local", path, "first_beat", image_prompt_id)`;
- `update_idea_status(idea_id, "image_generated")` (строго после записи);
- `_advance(state, 8, {idea_id, idea_name})`.

После шага статус `image_generated` → диспетчер ведёт на шаг 9 (как и «yes»-ветка шага 7).

### Test cases
- happy path (мок `fetch_idea_by_status`→idea, `fetch_rows`→scenarios `[{"id":3}]` и
  image_prompts `[{"id":9,...}]`, `generate_first_beat_image`→путь): вызваны
  `insert_image("local", <path>, "first_beat", 9)` и
  `update_idea_status(idea_id, "image_generated")`; `pipeline_step == 9`, `8 in executed_steps`
- идеи нет: `generate_first_beat_image`/`insert_image` не вызваны; `pipeline_step == 9`,
  `8 in executed_steps`
- нет image_prompt (scenario/prompt отсутствует): генерация и запись не вызваны; advance

## `s9_audio_prompts(state) -> dict`
Шаг 9: по идее со статусом `image_generated` генерирует через ИИ промпты **аудио-сегментов**
(для TTS) и их **битов** для сценария, сохраняет их в `audio_seg_prompts` + `audio_beat_prompts`
(заменяя прежние, `replace_audio_prompts`), переводит идею в `audio_prompts_finished`. Узел
самодостаточен (не доверяет state).

Поток:
- `idea = fetch_idea_by_status("image_generated")`; если `not idea["exists"]` — защитный
  `_advance(state, 9)` без работы (и без `interrupt`);
- `scenario_row = (fetch_rows("scenarios","idea", idea_id) or [{}])[0]`;
  `scenario_text = scenario_row.get("scenario","")`, `scenario_id = scenario_row.get("id")`;
- `existing = fetch_rows("audio_seg_prompts","scenario", scenario_id)` если `scenario_id`, иначе `[]`;
- **если `existing` непусто** → `interrupt("STATE 9 — Found N existing … [1] Continue to next step
  [2] Generate new\nChoose (1/2):")`:
  - `choice.strip() == "1"` → `update_idea_status(idea_id, "audio_prompts_finished")`,
    `_advance(state, 9, {idea_id, idea_name})` (на шаг 10) — генерации/записи нет;
  - иначе («2») → проваливается в генерацию;
- **генерация** (нет `existing` ИЛИ выбран «2»): `result = generate_audio_prompts(scenario_text)`;
  если `scenario_id is not None`: `replace_audio_prompts(result.get("audio_segments") or [],
  result.get("beats") or [], scenario_id)`, затем `update_idea_status(idea_id,
  "audio_prompts_finished")` (статус — строго ПОСЛЕ записи);
- `_advance(state, 9, {idea_id, idea_name})`.

`interrupt` — только при наличии `existing` и ПОСЛЕ guard'а (read-операции идемпотентны при resume).

### Test cases
- existing + «1» (мок `fetch_idea_by_status`→idea, `fetch_rows`→scenario `[{"id":3}]` и
  audio_seg_prompts `[{...}]`, `interrupt`→"1"): `generate_audio_prompts`/`replace_audio_prompts`
  НЕ вызваны; вызван `update_idea_status(idea_id, "audio_prompts_finished")`; `pipeline_step == 10`,
  `9 in executed_steps`
- existing + «2»: вызваны `generate_audio_prompts("SCEN")`,
  `replace_audio_prompts(segments, beats, 3)`, `update_idea_status(idea_id,
  "audio_prompts_finished")`; `pipeline_step == 10`, `9 in executed_steps`
- нет existing (audio_seg_prompts `[]`): `interrupt` НЕ вызван; вызваны generate+replace+update;
  advance
- идеи нет: `pipeline_step == 10`, `9 in executed_steps`; `interrupt`/`generate_audio_prompts` не вызваны

## `s10_generate_audio(state) -> dict`
Шаг 10: по идее со статусом `audio_prompts_finished` синтезирует речь по строкам
`audio_seg_prompts` через Google Gemini TTS (`services.audio_tts.generate_segment_audio`),
сохраняет WAV в `AUDIO_DIR`, регистрирует каждый сегмент в таблице `audio` (`insert_audio`) и
переводит идею в `audio_generated`. Узел самодостаточен (не доверяет state), полностью
автоматический (без `interrupt`). Статус меняется ТОЛЬКО после успешной генерации и записи всех
сегментов — при ошибке `generate_segment_audio`/`insert_audio` исключение пробрасывается, статус
и курсор не двигаются.

Поток:
- `idea = fetch_idea_by_status("audio_prompts_finished")`; если `not idea["exists"]` —
  защитный `_advance(state, 10)` без работы;
- `scenario_row = (fetch_rows("scenarios","idea", idea_id) or [{}])[0]`;
  `scenario_id = scenario_row.get("id")`;
- `segments = fetch_rows("audio_seg_prompts","scenario", scenario_id)` если `scenario_id`, иначе `[]`;
- если `scenario_id is not None`: для каждого `seg` — **посегментная идемпотентность**: если
  `fetch_rows("audio","seg_id", seg["seg_id"])` непусто (аудио уже сохранено), сегмент
  **пропускается** (без генерации/вставки); иначе `path = generate_segment_audio(seg, idea_id)`,
  `insert_audio("local", path, "segment", seg["seg_id"])`; затем
  `update_idea_status(idea_id, "audio_generated")` (строго после записей);
- `_advance(state, 10, {idea_id, idea_name})`.

Авто-пропуск без `interrupt`: покрывает полный повтор (всё уже есть → ничего не генерим, просто
метим статус) и частичный сбой (досинтезируем только недостающее, без дублей в `audio`).
После шага статус `audio_generated` → диспетчер ведёт на шаг 11.

### Test cases
- happy path (мок `fetch_idea_by_status`→idea, `fetch_rows`→scenarios `[{"id":3}]`,
  audio_seg_prompts `[{"seg_id":11,...},{"seg_id":12,...}]`, audio→`[]`, `generate_segment_audio`→путь):
  `generate_segment_audio` вызван на каждый сегмент, `insert_audio("local", <path>, "segment",
  seg_id)` на каждый; вызван `update_idea_status(idea_id, "audio_generated")`; `pipeline_step == 11`,
  `10 in executed_steps`
- частичный повтор (audio для seg_id=11 непусто, для seg_id=12 пусто): генерация/вставка вызваны
  **только** для seg_id=12; вызван `update_idea_status(idea_id, "audio_generated")`; advance
- всё уже есть (audio непусто для всех): `generate_segment_audio`/`insert_audio` не вызваны;
  `update_idea_status(idea_id, "audio_generated")` вызван; advance
- идеи нет: `generate_segment_audio`/`insert_audio`/`update_idea_status` не вызваны;
  `pipeline_step == 11`, `10 in executed_steps`
- нет сценария (`fetch_rows`→`[]`): генерация/запись/смена статуса не вызваны; advance

## `s11_generate_beats(state) -> dict`
Шаг 11: по идее со статусом `audio_generated` нарезает каждый синтезированный аудио-сегмент на
биты (forced alignment через `services.audio_beats.slice_segment_beats` → `aeneas`), сохраняет
по-битовые WAV в `AUDIO_DIR/beats`, регистрирует их в таблице `audio_beats` (`insert_audio_beat`,
с реальной `duration`) и переводит идею в `audio_beats_generated`. Узел самодостаточен, полностью
автоматический (без `interrupt`). Статус меняется ТОЛЬКО после успешной нарезки и записи — при
ошибке `slice_segment_beats`/`insert_audio_beat` исключение пробрасывается, статус и курсор не двигаются.

Поток:
- `idea = fetch_idea_by_status("audio_generated")`; если `not idea["exists"]` — защитный
  `_advance(state, 11)` без работы;
- `scenario_id` из `fetch_rows("scenarios","idea", idea_id)`; `segments =
  fetch_rows("audio_seg_prompts","scenario", scenario_id)` (иначе `[]`);
- если `scenario_id is not None`: для каждого `seg` (`seg_id = seg["seg_id"]`):
  - `audio_rows = fetch_rows("audio","seg_id", seg_id)`; если пусто — сегмент не озвучен, пропуск;
  - `beats = sorted(fetch_rows("audio_beat_prompts","seg_id", seg_id), key=id)`,
    `voiced = [b for b in beats if b["audio_text"].strip()]`; если пусто — силент-сегмент, пропуск;
  - **посегментная идемпотентность**: `already = [bool(fetch_rows("audio_beats","beat", b["id"]))
    for b in voiced]`; если `all(already)` — сегмент уже нарезан, `skipped += 1`, пропуск; если
    `any(already)` — частично, `delete_audio_beats_for_beats([b["id"] ...])` перед перенарезкой;
  - `manifest = slice_segment_beats(audio_rows[0]["key"], voiced, idea_id, seg_id)`; на каждый
    элемент `insert_audio_beat("local", item["path"], "beat", item["duration"], item["beat_id"])`;
  - затем `update_idea_status(idea_id, "audio_beats_generated")` (строго после записей);
- `_advance(state, 11, {idea_id, idea_name})`.

После шага статус `audio_beats_generated` → диспетчер ведёт на шаг 12.

### Test cases
- happy path (мок: scenarios `[{"id":3}]`, audio_seg_prompts `[{"seg_id":11},{"seg_id":12}]`,
  audio→`[{"key":...}]`, audio_beat_prompts→биты, audio_beats→`[]`, `slice_segment_beats`→манифест):
  `slice_segment_beats` вызван на сегмент, `insert_audio_beat` на каждый бит манифеста; вызван
  `update_idea_status(idea_id, "audio_beats_generated")`; `pipeline_step == 12`, `11 in executed_steps`
- посегментный пропуск (audio_beats непусто для всех битов сегмента): `slice_segment_beats`/
  `insert_audio_beat` не вызваны для него; статус всё равно метится
- частичная перенарезка (часть битов сегмента уже в audio_beats): вызван
  `delete_audio_beats_for_beats([...])`, затем нарезка и вставка
- идеи нет: `slice_segment_beats`/`insert_audio_beat`/`update_idea_status` не вызваны; advance до 12
- нет сценария (`fetch_rows`→`[]`): нарезка/запись/смена статуса не вызваны; advance

## Стабы шагов 12–13 — фабрика `_make_stub(n)`
Возвращает узел `stub(state)`: печатает `STATE {n} — (заглушка) ...` (имя идеи берёт через
`fetch_idea_by_status(IDEAS_STATUSES[n-5])`) и возвращает `_advance(state, n)`.

### Test cases
- `_make_stub(12)(state)` (мок `fetch_idea_by_status`): результат `pipeline_step == 13`,
  `12 in executed_steps`; в stdout `STATE 12`

## Поток графа
```
START → s1 → (s2) → s3 → dispatch
dispatch → _route_dispatch → s4 | s5..s13 | END
s4 → _route_s4 → s4_pick | dispatch
s4_pick → dispatch
s5..s13 → dispatch
```
`_route_s4`: `generated_ideas` есть → `"s4_pick"`, иначе → `"dispatch"`.
`_route_s5` удалён (его роль перешла диспетчеру).

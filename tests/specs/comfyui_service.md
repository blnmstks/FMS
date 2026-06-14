# Spec: `app/services/comfyui`

Оркестрация генерации изображения (шаг 8) и видео-клипов (шаг 13) через ComfyUI: собирает
`utils/workflow` + `utils/audio` + `infrastructure/comfyui_client`. Решения и порядок шагов
живут здесь.

## `generate_image(workflow_path, prompt_text, prompt_node_id, output_path, image_path=None, image_node_id=None, poll_interval=1.0, timeout=DEFAULT_TIMEOUT) -> str`

`DEFAULT_TIMEOUT = 300.0` — дефолт подобран под медленные модели (Flux: загрузка модели +
сэмплинг легко дольше 30с). Слишком короткий таймаут приводит к `TimeoutError` до скачивания,
и копия в проект не пишется (хотя ComfyUI у себя картинку сохраняет нодой SaveImage).

### Contract
1. `wf = load_workflow(workflow_path)`.
2. `set_node_input(wf, prompt_node_id, "text", prompt_text)`.
3. Если задан `image_path`: `name = upload_image(image_path)["name"]`, затем
   `set_node_input(wf, image_node_id, "image", name)`.
4. `client_id = uuid4().hex`; `prompt_id = queue_prompt(wf, client_id)`.
5. Polling `get_history(prompt_id)` каждые `poll_interval` сек, пока в
   `history[prompt_id]["outputs"]` не появится выходной файл. По истечении `timeout` —
   `TimeoutError`.
6. Берётся первый выходной файл через `_first_output_file` (первая нода, первый элемент по
   ключу `images`/`gifs`/`videos`): `{filename, subfolder, type}`.
7. `data = download_image(filename, subfolder, type)`; байты пишутся в `output_path`
   (родительская папка создаётся при необходимости).
8. Возвращает `output_path`.

### Invariants
1. Промпт всегда подставляется в ноду `prompt_node_id` под ключ `text` до отправки.
2. `upload_image` вызывается **только** при непустом `image_path`; тогда имя файла
   пишется в `image_node_id` под ключ `image`.
3. Без `image_path` ни `upload_image` не вызывается, ни нода изображения не трогается.
4. В `output_path` записываются ровно байты, вернувшиеся из `download_image`.
5. Возвращается `output_path`.
6. Если за `timeout` результат не появился — поднимается `TimeoutError`, файл не пишется.

## `build_prompt_text(image_prompt: dict) -> str`

### Contract
Объединяет непустые поля сохранённого image-prompt в порядке `IMAGE_PROMPT_FIELDS`
(`image_prompt, camera_angle, lighting, mood, action`) через `", "`. Пустые/отсутствующие
поля пропускаются. Лишние ключи строки БД (`id`, `scenario`, `created_at`) игнорируются.

### Invariants
1. Порядок частей соответствует `IMAGE_PROMPT_FIELDS`.
2. Пустые значения (`None`/`""`) не попадают в результат.

## `generate_first_beat_image(image_prompt: dict, idea_id: int) -> str`

### Contract
Бизнес-логика генерации картинки первого бита: собирает текст через `build_prompt_text`,
резолвит путь под `IMAGES_DIR` (имя `idea-<idea_id>-first-beat-<timestamp>.png`) и делегирует
в `generate_image(COMFYUI_WORKFLOW, prompt_text, COMFYUI_PROMPT_NODE, out)`. Возвращает путь
сохранённого файла.

### Invariants
1. `generate_image` вызывается с workflow и node id из конфига (`COMFYUI_WORKFLOW`,
   `COMFYUI_PROMPT_NODE`) и `prompt_text == build_prompt_text(image_prompt)`.
2. `output_path` лежит под `IMAGES_DIR` и содержит `idea-<idea_id>`.
3. Возвращает то, что вернул `generate_image`.

## `resolve_output_path(out: str | None, workflow_path: str, images_dir: str) -> str`

### Contract
Решает, куда писать копию изображения в проекте:
- `out` задан и **абсолютный** → возвращается как есть;
- `out` задан и **относительный** → кладётся внутрь `images_dir` (`Path(images_dir) / out`);
- `out` пуст (`None`/`""`) → дефолтное имя `"<workflow-stem>-<timestamp>.png"` внутри
  `images_dir`.

### Invariants
1. Абсолютный `out` не модифицируется.
2. Относительный `out` всегда оказывается под `images_dir`.
3. При пустом `out` имя содержит stem workflow-файла и оканчивается на `.png`, путь — под
   `images_dir`.

## `_first_output_file(outputs: dict) -> dict | None`

### Contract
Возвращает первый выходной файл из `outputs` (значения нод) по любому из ключей
`images`/`gifs`/`videos`: `{filename, subfolder, type}`. Нужен, потому что нода SaveVideo
кладёт результат под ключ, отличный от `images` (у картинок — `images`). Если файлов нет —
`None`. Общий для `generate_image` и `generate_beat_clip` (через `_wait_for_output`).

### Invariants
1. Перебор нод в порядке `outputs.values()`, ключей — `images`→`gifs`→`videos`.
2. Возвращает первый непустой `files[0]` либо `None`.

## `build_video_prompt_text(video_beat_prompt: dict, prev_end_frame: str | None = None) -> str`

### Contract
Собирает текст промпта клипа из строки `video_beat_prompts` БЛОКАМИ (разделитель `"\n\n"`),
чтобы LTX-2.3 видел стартовый кадр, финальный кадр и дисциплину камеры как отдельные обязательные
инструкции:
0. `STARTING FRAME\n<STARTING_FRAME_LEAD_SENTENCE>\n<prev_end_frame>` — ТОЛЬКО если `prev_end_frame`
   непуст (`end_frame` ПРЕДЫДУЩЕГО бита = буквальный входной freeze этого клипа = frame 0). Якорь
   против «прыжка» субъекта на стыке: LTX начинает движение ровно из этого состояния (поза рук,
   реквизит, мимика), а не доигрывает действие мгновенно. На первом бите `prev_end_frame=None`
   (старт = картинка шага 8) — блока нет. `STARTING_FRAME_LEAD_SENTENCE` — короткая утвердительная
   фраза-якорь (текст-константа в `app/prompts/video_prompts.py`); блок держится КОРОТКИМ, чтобы не
   пере-описывать статичную сцену (риск против I2V-минимализма).
1. `SHOT ACTION\n<video_prompt>` — если `video_prompt` непуст;
2. `MANDATORY FINAL FRAME\n<end_frame>\n<FINAL_FRAME_HOLD_SENTENCE>` — если `end_frame` непуст;
   `FINAL_FRAME_HOLD_SENTENCE` — одна УТВЕРДИТЕЛЬНАЯ фраза («лицо персонажа полностью видно,
   резко и читаемо в финальном кадре»). Запретительного списка («Do not end on lap, legs,
   jeans, hands, phone…») в позитивном промпте НЕТ и быть не должно: видеомодель не понимает
   отрицаний, токены запрещённых объектов работают как ПРИЗЫВ их нарисовать (наблюдалось:
   бит заканчивался ровно запрещённым torso-only кадром). Запреты остаются только в
   инструкции LLM шага 12 (`GENERATE_VIDEO_PROMPTS_PROMPT`) — LLM отрицания понимает.
3. `CAMERA DISCIPLINE\n…` — фиксированный текст дисциплины камеры (код-уровневая гарантия
   «tripod-first» на КАЖДЫЙ клип, независимая от поведения LLM шага 12): если move не описан явно
   в SHOT ACTION — камера на замке (no drift, no shake, no pan, no zoom, no reframing); явно
   описанный move обязан завершиться и осесть в статичный кадр до финального кадра. Добавляется
   при непустом `video_prompt`.
Пустые/отсутствующие поля пропускаются; лишние ключи строки БД (`id`, `beat`) игнорируются.
Все фиксированные тексты — константы `STARTING_FRAME_LEAD_SENTENCE`, `FINAL_FRAME_HOLD_SENTENCE` и
`CAMERA_DISCIPLINE_BLOCK` в `app/prompts/video_prompts.py` (промпт-текст живёт только в
`app/prompts/`).

### Invariants
1. Порядок блоков: STARTING FRAME → SHOT ACTION → MANDATORY FINAL FRAME (+hold-фраза) → CAMERA
   DISCIPLINE.
2. Пустые значения (`None`/`""`) не порождают свои блоки: без `prev_end_frame` нет блока STARTING
   FRAME (обратная совместимость — прежнее поведение); без `end_frame` нет блока 2 (и hold-фразы);
   без `video_prompt` нет блоков 1 и 3.
3. В результате НИКОГДА нет подстрок `FINAL-FRAME NEGATIVE CONSTRAINTS` и `Do not end on`.

## `generate_beat_clip(prompt_text, first_frame_path, audio_path, idea_id, beat_id, poll_interval=1.0, timeout=DEFAULT_VIDEO_TIMEOUT, seed=None) -> str`

`DEFAULT_VIDEO_TIMEOUT = 1800.0` — видео медленнее картинки (LTX-2.3: загрузка + сэмплинг +
апскейл).

### Contract
Бизнес-логика генерации видео-клипа одного бита (шаг 13):
1. `wf = load_workflow(COMFYUI_VIDEO_WORKFLOW)`.
2. `set_node_input(wf, COMFYUI_VIDEO_PROMPT_NODE, "value", prompt_text)`; затем печатает в консоль
   финальный positive prompt ровно из prompt-ноды (наглядный контроль того, что собрал
   `build_video_prompt_text` на каждый бит).
3. `name = upload_image(first_frame_path)["name"]`; `set_node_input(wf,
   COMFYUI_VIDEO_IMAGE_NODE, "image", name)`.
4. fps рендера берётся из `COMFYUI_VIDEO_FPS` (гайд LTX-2: 48–60 для плавности) и патчится в
   ноду `COMFYUI_VIDEO_FPS_NODE` (Frame Rate); та же частота идёт в snap — нода и математика
   кадров синхронны. `snapped = ltx_snap_duration(wav_duration_seconds(audio_path),
   COMFYUI_VIDEO_FPS)` — длительность, валидная для LTX (кадры `8n+1`, snap ВВЕРХ: видео никогда
   не короче речи; сырая длина молча резалась моделью ВНИЗ — хвост реплики мог обрезаться).
5. WAV паддится тишиной до `snapped` во ВРЕМЕННЫЙ файл (`pad_wav_to_duration`), и заливается
   именно он: `upload_audio(tmp)`; нода `COMFYUI_VIDEO_AUDIO_NODE["audio"]` получает его имя.
   Аудио- и видео-латенты совпадают по длине (TrimAudioDuration умеет только резать).
   Временный файл удаляется в `finally` (в т.ч. при `TimeoutError`).
6. `set_node_input(wf, COMFYUI_VIDEO_DURATION_NODE, "value", snapped)`.
7. Сиды: всем нодам `class_type == "RandomNoise"` (автопоиск, сортировка по node id)
   проставляется `noise_seed = base + i`, где `base = seed`, если передан, иначе
   `secrets.randbits(48)`. Сиды печатаются в консоль (воспроизводимость). Хардкод-сиды из
   JSON-файла больше не доезжают до сервера НИКОГДА: одинаковый шум на всех битах давал
   повторяющиеся артефакты, а ретрай воспроизводил тот же брак.
8. `prompt_id = queue_prompt(wf, uuid4().hex)`; ждём `_wait_for_output(...)`.
9. `data = download_image(filename, subfolder, type)`; пишем в
   `VIDEOS_DIR/clips/idea-<idea_id>-beat-<beat_id>-<timestamp><ext>` (ext — из имени файла
   ComfyUI, иначе `.mp4`), создавая папку.
10. `mux_clip_audio(out, tmp)` — дорожка клипа заменяется на исходный (паддированный) TTS-WAV
    (выход ComfyUI — голос после Audio-VAE-нейрокодека, деградация), метаданные срезаются
    (`-map_metadata -1` — иначе в MP4 утекает полный ComfyUI-граф). Возвращает путь клипа.

### Invariants
1. Промпт всегда в `COMFYUI_VIDEO_PROMPT_NODE["value"]`; первый кадр через `upload_image` в
   `COMFYUI_VIDEO_IMAGE_NODE["image"]`.
2. В `COMFYUI_VIDEO_DURATION_NODE["value"]` кладётся `ltx_snap_duration(wav_duration_seconds(
   audio_path), COMFYUI_VIDEO_FPS)`; в `COMFYUI_VIDEO_FPS_NODE["value"]` — `COMFYUI_VIDEO_FPS`;
   в `upload_audio` уходит файл ровно этой длины (паддированный временный WAV, не оригинал).
3. ВСЕ ноды `RandomNoise` отправленного workflow получают свежие сиды (≠ значениям из файла);
   при `seed=N` результат детерминирован (`N`, `N+1`, …).
4. В выходной файл пишутся байты `download_image`, затем по нему вызывается `mux_clip_audio`
   с паддированным WAV; путь — под `VIDEOS_DIR/clips`, содержит `idea-<idea_id>-beat-<beat_id>`.
5. Если за `timeout` результат не появился — `TimeoutError`, файл не пишется; временный WAV
   удалён в любом исходе.

## Runnable-скрипт (`python -m app.services.comfyui`)
`argparse`: `--workflow`, `--prompt`, `--prompt-node` (обязательные); `--out`, `--image`,
`--image-node`, `--timeout` (опциональные, `--timeout` по умолчанию `DEFAULT_TIMEOUT`).
Путь резолвится через `resolve_output_path(args.out, args.workflow, IMAGES_DIR)` (по умолчанию
копия идёт в `assets/images`), затем вызывается `generate_image(...)` и печатается путь.

## Test cases (unit; функции клиента замоканы, файлы через `tmp_path`)
- **подставляет промпт**: `queue_prompt` получил workflow с `["<prompt-node>"]["inputs"]["text"] == prompt_text`.
- **с image_path**: `upload_image` вызван с путём; `["<image-node>"]["inputs"]["image"]` == возвращённое имя.
- **без image_path**: `upload_image` не вызван.
- **сохраняет файл**: в `output_path` лежат байты из `download_image`; функция вернула `output_path`.
- **resolve абсолютный**: `resolve_output_path("/abs/x.png", wf, "assets/images") == "/abs/x.png"`.
- **resolve относительный**: `resolve_output_path("x.png", wf, "assets/images")` → `assets/images/x.png`.
- **resolve дефолт**: `resolve_output_path(None, ".../portrait_001.json", "assets/images")` →
  начинается с `assets/images`, содержит `portrait_001`, оканчивается на `.png`.
- **build_prompt_text**: для строки со всеми полями → части в порядке полей через ", ";
  пустые поля пропускаются.
- **generate_first_beat_image**: `patch` `generate_image` → вызван с `COMFYUI_WORKFLOW`,
  `COMFYUI_PROMPT_NODE`, `prompt_text == build_prompt_text(...)`, `output_path` под `IMAGES_DIR`
  и содержит `idea-7`; возврат пробрасывается.
- **_first_output_file**: находит файл под `gifs`/`videos` (не только `images`); пустые
  `outputs` → `None`.
- **build_video_prompt_text**: для строки со всеми полями → блоки SHOT ACTION → MANDATORY FINAL
  FRAME (включая hold-фразу) → CAMERA DISCIPLINE (в этом порядке); подстрок «FINAL-FRAME NEGATIVE
  CONSTRAINTS» и «Do not end on» НЕТ; CAMERA DISCIPLINE содержит «locked» и «settles into a
  static hold»; пустой `end_frame` → только SHOT ACTION + CAMERA DISCIPLINE (без hold-фразы);
  пустой `video_prompt` и `end_frame` → пустая строка.
- **build_video_prompt_text c prev_end_frame**: при переданном `prev_end_frame` → блок STARTING
  FRAME (c `STARTING_FRAME_LEAD_SENTENCE` и текстом `prev_end_frame`) идёт ПЕРВЫМ, до SHOT ACTION;
  при `prev_end_frame=None`/`""` — блока STARTING FRAME нет (результат идентичен прежнему).
- **generate_beat_clip** (моки клиента + `mux_clip_audio`, реальный мини-WAV,
  `VIDEOS_DIR`/`COMFYUI_VIDEO_WORKFLOW`/`tempfile.gettempdir` замоканы на `tmp_path`; фикстура
  workflow содержит две ноды `RandomNoise` с «хардкодными» сидами): промпт в prompt-ноде;
  `upload_image`(first_frame)+image-нода; `upload_audio` вызван с ПАДДИРОВАННЫМ временным WAV
  (длина == snap, проверяется side_effect-ом в момент вызова); duration-нода ==
  `ltx_snap_duration(wav_duration_seconds(audio))`; обе RandomNoise-ноды получили новые сиды
  (≠ исходным, разные между собой), `seed=123` → сиды `123`/`124`; байты из `download_image`
  записаны под `VIDEOS_DIR/clips/...`, путь содержит `idea-<id>-beat-<id>`; `mux_clip_audio`
  вызван с (путь клипа, паддированный WAV); временный WAV удалён; пустой `outputs` →
  `TimeoutError`, файл не пишется, временный WAV удалён.

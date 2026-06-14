# Spec: `app/services/clip_qc`

QC-гейт шага 13. Сцепка клипов идёт по последнему кадру: один бракованный финальный кадр
(лицо закрыто графикой, безголовый торс, «подменённый» персонаж) заражает все следующие биты —
наблюдалось на idea-1 (бит 3 кончился торсом без головы, бит 4 «восстановился» другим
человеком). Сервис смотрит референс персонажа (картинка шага 8) и три кадра клипа vision-LLM
и выносит вердикт ДО того, как клип попадёт в сцепку/БД.

## `qc_frame_paths(clip_path: str) -> list[str]`

### Contract
Возвращает пути трёх QC-кадров клипа в порядке `[first, mid, last]`:
`VIDEOS_DIR/frames/qc/<stem>-{first,mid,last}.png`, где `<stem>` — имя клипа без расширения.
Единый источник имён: используется и при извлечении кадров (`review_clip`), и при уборке
зафейленных клипов узлом шага 13 (чтобы по пути клипа знать его QC-кадры).

### Invariants
1. Ровно 3 пути в порядке first, mid, last.
2. Все под `VIDEOS_DIR/frames/qc/`, имена `<stem>-first.png` / `-mid.png` / `-last.png`.

### Test cases (unit)
- для `clips/idea-1-beat-3-ts.mp4` → `[…/frames/qc/idea-1-beat-3-ts-first.png, …-mid.png,
  …-last.png]` (под замоканным `VIDEOS_DIR`).

## `review_clip(clip_path: str, reference_image_path: str, duration_seconds: float) -> dict`

### Contract
1. Извлекает кадры клипа в `VIDEOS_DIR/frames/qc/` (остаются на диске — инспектируемы), пути —
   из `qc_frame_paths(clip_path)`:
   - `<stem>-first.png` — `extract_frame_at(clip_path, 0.0, …)`;
   - `<stem>-mid.png` — `extract_frame_at(clip_path, duration_seconds / 2, …)`;
   - `<stem>-last.png` — `extract_last_frame(clip_path, …)`.
2. Один vision-вызов (паттерн `visual_styles`): `get_client()`, content =
   `[{"type":"text","text": CLIP_QC_PROMPT}] + encode_images([reference, first, mid, last])`
   — порядок изображений фиксирован промптом (REFERENCE первым); system — «You are a JSON
   API…»; `model=DEFAULT_MODEL`; `response_format={"type":"json_object"}`.
3. Парсит ответ `json.JSONDecoder().raw_decode(...)` → dict вида
   `{face_visible_in_final_frame, same_character_as_reference, severe_artifacts,
   verdict: "pass"|"fail", reason}`; печатает вердикт и usage; возвращает dict.
4. `log_llm_input` НЕ используется (он печатает messages целиком — мегабайты base64).

### Invariants
1. Кадры first/mid извлекаются на `0.0` и `duration_seconds/2`; last — `extract_last_frame`.
2. В `encode_images` уходит ровно `[reference_image_path, first, mid, last]` (референс первым).
3. `response_format={"type":"json_object"}`, модель — `DEFAULT_MODEL`.
4. Возвращается распарсенный dict ответа как есть (вердикт интерпретирует вызывающий код).
5. Невалидный JSON ответа — исключение наверх (`json.JSONDecodeError`), не глотается.

### Test cases (unit; `get_client`/`extract_frame_at`/`extract_last_frame`/`encode_images`
замоканы, ответ — фикстура `mock_llm_response`)
- **кадры**: `extract_frame_at` вызван дважды — (clip, 0.0, …-first.png) и
  (clip, duration/2, …-mid.png); `extract_last_frame` — (clip, …-last.png); пути под
  `VIDEOS_DIR/frames/qc/`.
- **порядок изображений**: `encode_images` вызван с `[reference, first, mid, last]`.
- **vision-вызов**: первый элемент content — текст `CLIP_QC_PROMPT`, далее картинки;
  `response_format={"type":"json_object"}`.
- **возврат**: dict ответа пробрасывается как есть (`verdict == "fail"` и т.п.).
- **кривой JSON**: ответ «не JSON» → `json.JSONDecodeError`.

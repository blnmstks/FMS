# Spec: `comfyui_workflows/*.json` (guard-инварианты ассетов)

Workflow-файлы — экспорт из ComfyUI (API-format). Их легко молча сломать пере-экспортом
(меняются префиксы subgraph-нод, теряются ручные правки значений). Этот спек фиксирует
значения, от которых зависит код шагов 8/13 и качество клипов; guard-тест читает РЕАЛЬНЫЕ
JSON-файлы из `app/config.py` (`COMFYUI_VIDEO_WORKFLOW`, `COMFYUI_IMAGE_WORKFLOW`).

## `video_ltx2_3_ia2v_api.json`

### Invariants
1. Все ноды `LTXVImgToVideoInplace` имеют `strength == 1.0` — стартовый кадр пиннится
   жёстко на обоих проходах. При 0.7 модель сразу уплывает от входного кадра, и стыки
   битов «пыхают» (замерено SSIM 0.58–0.68 между last/first кадрами соседних клипов).
2. Ноды размеров (`PrimitiveInt` с titles `Width`/`Height`): `1024×576`, оба кратны 64.
   Первый проход рендерится на половинном разрешении (нода `a/2`), латенту нужны
   пиксельные размеры кратные 32 → полное разрешение кратно 64. `720` невалидно: модель
   молча режет до 704 (AR 16:11). `1024×576` — честный 16:9 для YouTube.
3. Нода `Frame Rate` (id = `COMFYUI_VIDEO_FPS_NODE`) существует и патчабельна (вход `value`):
   fps задаётся из конфига `COMFYUI_VIDEO_FPS` и патчится перед отправкой, значение в JSON — лишь
   дефолт. Та же частота идёт в `ltx_snap_duration`, поэтому кадры остаются `8n+1`.
4. Ноды из конфига существуют и имеют ожидаемые ключи входов:
   `COMFYUI_VIDEO_PROMPT_NODE` → `value`, `COMFYUI_VIDEO_IMAGE_NODE` → `image`,
   `COMFYUI_VIDEO_AUDIO_NODE` → `audio`, `COMFYUI_VIDEO_DURATION_NODE` → `value`.
5. Есть хотя бы одна нода `RandomNoise` с входом `noise_seed` — на автопоиск этих нод
   опирается пер-запусковый патч сидов в `generate_beat_clip`.

## `portrait_001.json` (картинка шага 8)

### Invariants
1. Латент (нода `EmptyFlux2LatentImage`) и шедулер (нода `Flux2Scheduler`) — `1024×576`:
   AR совпадает с видео-workflow (он центр-кропит входную картинку; квадрат 480×480
   давал мутный анкор и потерю композиции).

## Test cases (unit)
- video: каждый `LTXVImgToVideoInplace.strength == 1.0`.
- video: Width/Height == 1024/576 и `% 64 == 0`; Frame Rate == 24.
- video: все четыре config-ноды существуют, ключи входов на месте.
- video: список `RandomNoise`-нод непуст, у всех есть `noise_seed`.
- portrait: обе размерные ноды 1024×576.

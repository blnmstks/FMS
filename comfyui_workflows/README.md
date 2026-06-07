## Ручная отправка

ComfyUI должен быть запущен по адресу из `COMFYUI_URL` в `.env` (по умолчанию
`http://127.0.0.1:8188`). Картинка скачивается в проект, в `assets/images`
(каталог из `IMAGES_DIR`, создаётся автоматически). При этом ComfyUI ещё и сам сохраняет
результат у себя в `output/` — это нода `SaveImage`, так и должно быть.

`--out` опционален: относительные пути кладутся внутрь `assets/images`, без `--out` имя
формируется как `<workflow>-<timestamp>.png`.

Базовый запуск (имя по умолчанию → `assets/images/portrait_001-<ts>.png`):
`python -m app.services.comfyui --workflow comfyui_workflows/portrait_001.json --prompt "a red fox" --prompt-node 4`

С явным именем (ляжет в `assets/images/fox.png`) и большим таймаутом (Flux медленный):
`python -m app.services.comfyui --workflow comfyui_workflows/portrait_001.json --prompt "a red fox" --prompt-node 4 --out fox.png --timeout 600`

С подменой картинки:
`python -m app.services.comfyui --workflow wf.json --prompt "..." --prompt-node 6 --out out.png --image in.png --image-node 10`

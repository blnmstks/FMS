# v3. Прежняя формулировка («изобрази открывающие 3-5 секунд скрипта») давала иллюстративную
# хук-сцену БЕЗ ведущего (на idea-1 — персонаж за рулём машины), а видео-промпт бита 1 описывал
# talking-head за столом → первые полсекунды клипа превращались в морф-артефакт. Картинка —
# открывающая МАСТЕР-КАДРОВКА: буквальный входной кадр первого клипа (I2V анимирует ровно её)
# и референс идентичности персонажа на всю цепочку. v3: убран призыв «supporting graphics» и
# добавлен запрет читаемого текста/мелких иконок — LTX-2 их не удерживает в движении, а стартовый
# кадр якорит всю цепочку (на роликах текст/иконки превращались в кашу).
GENERATE_IMAGE_PROMPT_PROMPT = (
    "You are a visual director generating the OPENING FRAME image prompt for a short-form\n"
    "talking-head video. You are given the full scenario, the Visual Style Profile, and the\n"
    "locked Character Reference Sheet.\n\n"
    "What this image is used for (this dictates every rule):\n"
    "- It is the literal INPUT FRAME of the first video clip: an image-to-video model will\n"
    "  animate the opening beat starting from exactly this picture.\n"
    "- It is also the IDENTITY REFERENCE for the whole video: every later clip inherits the\n"
    "  character's face from it through a chain of frames.\n\n"
    "Rules:\n"
    "- Depict the opening MASTER FRAMING of the video, not an illustrative hook scene: the\n"
    "  primary character is ON SCREEN, in the setting where they deliver the script's opening\n"
    "  lines.\n"
    "- The character's face is fully visible, sharp, front or 3/4, and large enough to read\n"
    "  identity; appearance follows the locked Character Reference Sheet exactly.\n"
    "- A stable, deliberate, settled composition (medium shot preferred): no mid-action\n"
    "  freeze, no motion blur, no extreme close-up, no wide shot where the face is small.\n"
    "- Leave clean negative space beside the character (for composition), but put NO readable\n"
    "  text, words, numbers, captions, labels, logos, UI or small detailed icons anywhere in the\n"
    "  image: the image-to-video model cannot keep text and it degrades into scribble downstream.\n"
    "  If a supporting visual is unavoidable, make it ONE large, simple, text-free shape.\n"
    "- The prompt must be fully standalone and follow the Visual Style Profile exactly.\n\n"
    "Output only valid JSON (no commentary, no markdown). Shape:\n"
    "{\n"
    '  "image_prompt": "...",\n'
    '  "camera_angle": "...",\n'
    '  "lighting": "...",\n'
    '  "mood": "...",\n'
    '  "action": "..."\n'
    "}"
)

import os

from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ["DB_URL"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
DEFAULT_MODEL = os.environ["DEFAULT_MODEL"]
THREAD_ID = "proj-1"
VAULT_PATH = os.environ.get("VAULT_PATH", "vault")
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
IMAGES_DIR = os.environ.get("IMAGES_DIR", "assets/images")
COMFYUI_IMAGE_WORKFLOW = os.environ.get("COMFYUI_WORKFLOW", "comfyui_workflows/portrait_001.json")
COMFYUI_IMAGE_PROMPT_NODE = os.environ.get("COMFYUI_PROMPT_NODE", "4")

# Видео-генерация (шаг 13, LTX-2.3). Workflow — в API-format (Export API из ComfyUI; UI-формат
# с subgraph эндпоинт /prompt не принимает). Id нод сверены с реальным экспортом
# video_ltx2_3_ia2v_api.json: верхнеуровневые ноды сохраняют id (LoadImage 269, LoadAudio 276),
# а ноды развёрнутого subgraph получают префикс инстанса "340:" (prompt 340:319, duration 340:331).
# При новом экспорте префикс может смениться — тогда поправить тут или через env.
# Ключи входов: prompt→value, image→image, audio→audio, duration→value.
VIDEOS_DIR = os.environ.get("VIDEOS_DIR", "assets/videos")
COMFYUI_VIDEO_WORKFLOW = os.environ.get(
    "COMFYUI_VIDEO_WORKFLOW", "comfyui_workflows/video_ltx2_3_ia2v_api.json"
)
COMFYUI_VIDEO_PROMPT_NODE = os.environ.get("COMFYUI_VIDEO_PROMPT_NODE", "340:319")
COMFYUI_VIDEO_IMAGE_NODE = os.environ.get("COMFYUI_VIDEO_IMAGE_NODE", "269")
COMFYUI_VIDEO_AUDIO_NODE = os.environ.get("COMFYUI_VIDEO_AUDIO_NODE", "276")
COMFYUI_VIDEO_DURATION_NODE = os.environ.get("COMFYUI_VIDEO_DURATION_NODE", "340:331")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview")
AUDIO_DIR = os.environ.get("AUDIO_DIR", "assets/audio")
DEFAULT_TTS_VOICE = os.environ.get("DEFAULT_TTS_VOICE", "Achird")

# Стабильная карта «спикер → пресетный голос Gemini». Источник истины для resolve_voice.
# Achird - google name. Narrator - from scenario
SPEAKER_VOICE_MAP = {
    "Narrator": "Achird",
}

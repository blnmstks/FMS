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

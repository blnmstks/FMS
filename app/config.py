import os

from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ["DB_URL"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
DEFAULT_MODEL = os.environ["DEFAULT_MODEL"]
THREAD_ID = "proj-1"

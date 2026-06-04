from openai import OpenAI
from app.config import OPENROUTER_API_KEY

def get_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

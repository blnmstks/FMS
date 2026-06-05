import json

from openai import OpenAI

from app.config import OPENROUTER_API_KEY


def get_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )


def log_llm_input(messages: list) -> None:
    # Выводит в консоль итоговый инпут (messages), который уходит в LLM, — ровно как есть.
    print("\n================ LLM INPUT (messages) ================")
    print(json.dumps(messages, ensure_ascii=False, indent=2))
    print("======================================================\n")

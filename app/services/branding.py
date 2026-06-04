import json
import random

from app.config import DEFAULT_MODEL
from app.infrastructure.llm_client import get_client
from app.prompts.branding import DEFINE_BRAND_ID_PROMPT
from app.utils.images import encode_images


def analyze_channel(channel_name: str, screenshot_paths: list[str]) -> dict:
    client = get_client()
    images = encode_images(screenshot_paths)
    content = [
        {"type": "text", "text": f"Channel name: {channel_name}\n\n{DEFINE_BRAND_ID_PROMPT}"}
    ] + images

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a JSON API. Respond only with valid JSON, no markdown, no commentary.",
            },
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )

    usage = response.usage
    print(
        f"\n[LLM usage] input: {usage.prompt_tokens} tokens | "
        f"output: {usage.completion_tokens} tokens | "
        f"total: {usage.total_tokens} tokens"
    )

    brief, _ = json.JSONDecoder().raw_decode(response.choices[0].message.content.strip())
    return {
        "channel_name": random.choice(brief["channel_name_variants"]),
        "channel_description": random.choice(brief["channel_description_variants"]),
        "channel_avatar": brief["channel_avatar_prompt"],
        "channel_banner": brief["channel_banner_prompt"],
        "channel_info_complete": True,
    }

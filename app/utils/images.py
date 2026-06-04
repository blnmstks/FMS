import base64
from pathlib import Path


def encode_images(paths: list[str]) -> list[dict]:
    result = []
    for raw in paths:
        p = Path(raw.strip())
        b64 = base64.standard_b64encode(p.read_bytes()).decode()
        ext = p.suffix.lstrip(".") or "jpeg"
        result.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/{ext};base64,{b64}"},
            }
        )
    return result

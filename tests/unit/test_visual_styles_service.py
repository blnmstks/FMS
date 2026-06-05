from unittest.mock import patch

import pytest

from app.db import VISUAL_STYLE_FIELDS


def _payload():
    data = {f: f"val_{f}" for f in VISUAL_STYLE_FIELDS}
    data["characters"] = [{"label": "Jack", "build": "tall"}]
    return data


@pytest.fixture
def _mock_deps(mock_llm_response):
    """Patch get_client and encode_images so no real I/O happens."""
    fake_response = mock_llm_response(_payload())
    with (
        patch("app.services.visual_styles.get_client") as mock_get_client,
        patch("app.services.visual_styles.encode_images", return_value=[]) as enc,
    ):
        mock_get_client.return_value.chat.completions.create.return_value = fake_response
        yield mock_get_client, enc


@pytest.mark.unit
def test_generate_visual_style_returns_all_fields(_mock_deps):
    from app.services.visual_styles import generate_visual_style

    result = generate_visual_style("Idea X", "SCEN", {"niche": "tech"}, ["a.jpg"])

    for field in VISUAL_STYLE_FIELDS:
        assert field in result
    assert "characters" in result


@pytest.mark.unit
def test_generate_visual_style_uses_json_response_format(_mock_deps):
    mock_get_client, _ = _mock_deps
    from app.services.visual_styles import generate_visual_style

    generate_visual_style("Idea X", "SCEN", {"niche": "tech"}, ["a.jpg"])

    create = mock_get_client.return_value.chat.completions.create
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.unit
def test_generate_visual_style_passes_images_and_data(_mock_deps):
    mock_get_client, enc = _mock_deps
    from app.services.visual_styles import generate_visual_style

    generate_visual_style("Idea X", "SCEN", {"niche": "tech"}, ["a.jpg", "b.jpg"])

    enc.assert_called_once_with(["a.jpg", "b.jpg"])
    create = mock_get_client.return_value.chat.completions.create
    messages = create.call_args.kwargs["messages"]
    user_content = messages[-1]["content"]
    text_block = next(b["text"] for b in user_content if b.get("type") == "text")
    assert "Idea X" in text_block
    assert "SCEN" in text_block
    assert "tech" in text_block

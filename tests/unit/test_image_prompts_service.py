from unittest.mock import patch

import pytest

from app.db import IMAGE_PROMPT_FIELDS


def _payload():
    return {f: f"val_{f}" for f in IMAGE_PROMPT_FIELDS}


@pytest.fixture
def _mock_client(mock_llm_response):
    """Patch get_client so no real I/O happens."""
    fake_response = mock_llm_response(_payload())
    with patch("app.services.image_prompts.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = fake_response
        yield mock_get_client


@pytest.mark.unit
def test_generate_image_prompt_returns_all_fields(_mock_client):
    from app.services.image_prompts import generate_image_prompt

    result = generate_image_prompt("SCEN", {"art_style": "anime"}, [{"label": "Jack"}])

    for field in IMAGE_PROMPT_FIELDS:
        assert field in result


@pytest.mark.unit
def test_generate_image_prompt_uses_json_response_format(_mock_client):
    from app.services.image_prompts import generate_image_prompt

    generate_image_prompt("SCEN", {"art_style": "anime"}, [{"label": "Jack"}])

    create = _mock_client.return_value.chat.completions.create
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.unit
def test_generate_image_prompt_passes_scenario_style_and_characters(_mock_client):
    from app.services.image_prompts import generate_image_prompt

    generate_image_prompt("SCEN", {"art_style": "anime"}, [{"label": "Jack"}])

    create = _mock_client.return_value.chat.completions.create
    messages = create.call_args.kwargs["messages"]
    user_content = messages[-1]["content"]
    assert "SCEN" in user_content
    assert "anime" in user_content
    assert "Jack" in user_content

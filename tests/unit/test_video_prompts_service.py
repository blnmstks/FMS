from unittest.mock import MagicMock, patch

import pytest


def _payload():
    return {
        "beats": [
            {"id": 1, "video_prompt": "vp one", "end_frame": "ef one"},
            {"id": 2, "video_prompt": "vp two", "end_frame": "ef two"},
        ]
    }


_BEATS = [
    {"id": 1, "audio_text": "Hello there", "duration": 3.2},
    {"id": 2, "audio_text": "Goodbye", "duration": 2.1},
]


@pytest.fixture
def _mock_client(mock_llm_response):
    """Patch get_client so no real I/O happens."""
    fake_response = mock_llm_response(_payload())
    with patch("app.services.video_prompts.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = fake_response
        yield mock_get_client


@pytest.mark.unit
def test_generate_video_prompts_returns_beats(_mock_client):
    from app.services.video_prompts import generate_video_prompts

    result = generate_video_prompts("SCEN", {"art_style": "anime"}, [{"label": "Jack"}], _BEATS)

    assert "beats" in result
    assert result["beats"][0]["video_prompt"] == "vp one"
    assert result["beats"][0]["end_frame"] == "ef one"


@pytest.mark.unit
def test_generate_video_prompts_uses_json_response_format(_mock_client):
    from app.services.video_prompts import generate_video_prompts

    generate_video_prompts("SCEN", {"art_style": "anime"}, [{"label": "Jack"}], _BEATS)

    create = _mock_client.return_value.chat.completions.create
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.unit
def test_generate_video_prompts_passes_scenario_style_characters_and_beats(_mock_client):
    from app.services.video_prompts import generate_video_prompts

    generate_video_prompts("SCEN", {"art_style": "anime"}, [{"label": "Jack"}], _BEATS)

    create = _mock_client.return_value.chat.completions.create
    user_content = create.call_args.kwargs["messages"][-1]["content"]
    assert "SCEN" in user_content
    assert "anime" in user_content
    assert "Jack" in user_content
    assert "Hello there" in user_content


@pytest.mark.unit
def test_generate_video_prompts_raises_on_bad_json():
    from app.services.video_prompts import generate_video_prompts

    bad_response = MagicMock()
    bad_response.choices[0].message.content = "not json at all"
    bad_response.usage.prompt_tokens = 1
    bad_response.usage.completion_tokens = 1
    bad_response.usage.total_tokens = 2

    import json

    with patch("app.services.video_prompts.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = bad_response
        with pytest.raises(json.JSONDecodeError):
            generate_video_prompts("SCEN", {}, [], _BEATS)

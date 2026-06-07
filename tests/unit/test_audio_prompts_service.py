import json
from unittest.mock import MagicMock, patch

import pytest

PAYLOAD = {
    "audio_segments": [
        {
            "seg_id": 1,
            "speaker": "Narrator",
            "emotion": "calm",
            "tts_text": "Hello world.",
            "beat_ids": [1, 2],
        }
    ],
    "beats": [
        {"id": 1, "seg_id": 1, "audio_text": "Hello"},
        {"id": 2, "seg_id": 1, "audio_text": " world."},
    ],
}


@pytest.fixture
def _mock_client(mock_llm_response):
    """Patch get_client so no real I/O happens."""
    fake_response = mock_llm_response(PAYLOAD)
    with patch("app.services.audio_prompts.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = fake_response
        yield mock_get_client


@pytest.mark.unit
def test_generate_audio_prompts_returns_both_arrays(_mock_client):
    from app.services.audio_prompts import generate_audio_prompts

    result = generate_audio_prompts("SCEN")

    assert "audio_segments" in result
    assert "beats" in result
    assert len(result["audio_segments"]) == 1
    assert len(result["beats"]) == 2


@pytest.mark.unit
def test_generate_audio_prompts_uses_json_response_format(_mock_client):
    from app.services.audio_prompts import generate_audio_prompts

    generate_audio_prompts("SCEN")

    create = _mock_client.return_value.chat.completions.create
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.unit
def test_generate_audio_prompts_passes_scenario(_mock_client):
    from app.services.audio_prompts import generate_audio_prompts

    generate_audio_prompts("SCEN")

    create = _mock_client.return_value.chat.completions.create
    messages = create.call_args.kwargs["messages"]
    user_content = messages[-1]["content"]
    assert "SCEN" in user_content


@pytest.mark.unit
def test_generate_audio_prompts_invalid_json_raises():
    bad = MagicMock()
    bad.choices[0].message.content = "not valid json {{{"
    bad.usage.prompt_tokens = 1
    bad.usage.completion_tokens = 1
    bad.usage.total_tokens = 2

    with patch("app.services.audio_prompts.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = bad
        from app.services.audio_prompts import generate_audio_prompts

        with pytest.raises(json.JSONDecodeError):
            generate_audio_prompts("SCEN")

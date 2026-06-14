import json
from unittest.mock import MagicMock, patch

import pytest

_REPAIRED = {"video_prompt": "vp fixed", "end_frame": "ef fixed"}
_VERDICT = {
    "face_visible_in_final_frame": False,
    "same_character_as_reference": True,
    "severe_artifacts": True,
    "verdict": "fail",
    "reason": "graphics spawn over the right side of the frame",
}


@pytest.fixture
def _mock_client(mock_llm_response):
    with patch("app.services.video_prompt_repair.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = mock_llm_response(
            _REPAIRED
        )
        yield mock_get_client


@pytest.mark.unit
def test_repair_video_prompt_uses_json_response_format_and_model(_mock_client):
    from app.config import DEFAULT_MODEL
    from app.services.video_prompt_repair import repair_video_prompt

    repair_video_prompt("vp old", "ef old", _VERDICT)

    create = _mock_client.return_value.chat.completions.create
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}
    assert create.call_args.kwargs["model"] == DEFAULT_MODEL


@pytest.mark.unit
def test_repair_video_prompt_sends_current_fields_and_reason(_mock_client):
    from app.services.video_prompt_repair import repair_video_prompt

    repair_video_prompt("vp old", "ef old", _VERDICT)

    content = _mock_client.return_value.chat.completions.create.call_args.kwargs["messages"][-1][
        "content"
    ]
    # текстовый вызов: content — строка с текущими полями и причиной отказа QC
    assert isinstance(content, str)
    assert "vp old" in content
    assert "ef old" in content
    assert "graphics spawn over the right side of the frame" in content


@pytest.mark.unit
def test_repair_video_prompt_returns_parsed_fields(_mock_client):
    from app.services.video_prompt_repair import repair_video_prompt

    result = repair_video_prompt("vp old", "ef old", _VERDICT)

    assert result == _REPAIRED


@pytest.mark.unit
def test_repair_video_prompt_raises_on_invalid_json():
    from app.services.video_prompt_repair import repair_video_prompt

    bad = MagicMock()
    bad.choices[0].message.content = "not json"
    with patch("app.services.video_prompt_repair.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = bad
        with pytest.raises(json.JSONDecodeError):
            repair_video_prompt("vp", "ef", _VERDICT)

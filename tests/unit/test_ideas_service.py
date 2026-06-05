import json
from unittest.mock import MagicMock, patch

import pytest

IDEAS = [f"Idea number {i}" for i in range(1, 11)]
VALID_PAYLOAD = {"ideas": IDEAS}

CHANNEL_STYLE = {
    "niche": "personal finance",
    "target_audience": "young adults",
    "hook_style": "bold question",
    "script_flow": "problem-solution",
    "sentence_rhythm": "short punchy",
    "tone": "friendly",
    "transitions": "smooth",
    "curiosity_gaps": "frequent",
    "emotional_triggers": "fear of missing out",
    "retention_techniques": "open loops",
    "direct_address": "you-focused",
    "words_per_second": "2.5",
    "average_word_count": "1200",
    "target_word_count": "1300",
}


@pytest.fixture
def _mock_llm(mock_llm_response):
    fake = mock_llm_response(VALID_PAYLOAD)
    with patch("app.services.ideas.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = fake
        yield mock_get_client


@pytest.mark.unit
def test_generate_video_ideas_returns_ten(_mock_llm):
    from app.services.ideas import generate_video_ideas

    result = generate_video_ideas(
        "MyChannel", "A finance channel", CHANNEL_STYLE, ["transcript one"]
    )

    assert len(result) == 10


@pytest.mark.unit
def test_generate_video_ideas_values_match_payload(_mock_llm):
    from app.services.ideas import generate_video_ideas

    result = generate_video_ideas(
        "MyChannel", "A finance channel", CHANNEL_STYLE, ["transcript one"]
    )

    assert result == IDEAS


@pytest.mark.unit
def test_generate_video_ideas_invalid_json_raises():
    bad = MagicMock()
    bad.choices[0].message.content = "not valid json {{{"
    bad.usage.prompt_tokens = 1
    bad.usage.completion_tokens = 1
    bad.usage.total_tokens = 2

    with patch("app.services.ideas.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = bad
        from app.services.ideas import generate_video_ideas

        with pytest.raises(json.JSONDecodeError):
            generate_video_ideas("MyChannel", "desc", CHANNEL_STYLE, ["t"])


@pytest.mark.unit
def test_generate_video_ideas_includes_channel_and_style_in_prompt(_mock_llm):
    from app.services.ideas import generate_video_ideas

    generate_video_ideas("MyChannel", "A finance channel", CHANNEL_STYLE, ["t"])

    create = _mock_llm.return_value.chat.completions.create
    sent = json.dumps(create.call_args.kwargs["messages"])
    assert "MyChannel" in sent
    assert "personal finance" in sent  # niche value
    assert "young adults" in sent  # target_audience value


@pytest.mark.unit
def test_generate_video_ideas_excludes_average_word_count_field():
    from app.services.ideas import IDEA_STYLE_FIELDS

    assert "average_word_count" not in IDEA_STYLE_FIELDS
    assert "target_word_count" in IDEA_STYLE_FIELDS

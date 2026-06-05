from unittest.mock import MagicMock, patch

import pytest

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


def _fake_text_response(text: str):
    response = MagicMock()
    response.choices[0].message.content = text
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    response.usage.total_tokens = 15
    return response


@pytest.fixture
def _mock_llm():
    fake = _fake_text_response("  SCENARIO TEXT  ")
    with patch("app.services.scenarios.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = fake
        yield mock_get_client


@pytest.mark.unit
def test_generate_scenario_returns_stripped_text(_mock_llm):
    from app.services.scenarios import generate_scenario

    result = generate_scenario(
        "My Idea", "MyChannel", "A finance channel", CHANNEL_STYLE, ["transcript one"]
    )

    assert result == "SCENARIO TEXT"


@pytest.mark.unit
def test_generate_scenario_does_not_use_response_format(_mock_llm):
    from app.services.scenarios import generate_scenario

    generate_scenario("My Idea", "MyChannel", "desc", CHANNEL_STYLE, ["t"])

    create = _mock_llm.return_value.chat.completions.create
    assert "response_format" not in create.call_args.kwargs


@pytest.mark.unit
def test_generate_scenario_includes_idea_style_and_transcripts_in_prompt(_mock_llm):
    import json

    from app.services.scenarios import generate_scenario

    generate_scenario(
        "My Idea", "MyChannel", "A finance channel", CHANNEL_STYLE, ["transcript one"]
    )

    create = _mock_llm.return_value.chat.completions.create
    sent = json.dumps(create.call_args.kwargs["messages"])
    assert "My Idea" in sent
    assert "personal finance" in sent  # niche value
    assert "transcript one" in sent


@pytest.mark.unit
def test_scenario_style_fields_exclude_average_word_count():
    from app.services.scenarios import SCENARIO_STYLE_FIELDS

    assert "average_word_count" not in SCENARIO_STYLE_FIELDS
    assert "target_word_count" in SCENARIO_STYLE_FIELDS


@pytest.mark.unit
def test_generate_scenario_prints_llm_input(_mock_llm, capsys):
    from app.services.scenarios import generate_scenario

    generate_scenario("My Idea", "MyChannel", "desc", CHANNEL_STYLE, ["transcript one"])

    out = capsys.readouterr().out
    assert "My Idea" in out
    assert "personal finance" in out  # niche value
    assert "transcript one" in out

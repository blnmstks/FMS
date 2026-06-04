import json
from unittest.mock import MagicMock, patch

import pytest

from app.db import STYLE_FIELDS

VALID_PAYLOAD = {field: f"value_{field}" for field in STYLE_FIELDS}


@pytest.fixture
def _mock_llm(mock_llm_response):
    fake = mock_llm_response(VALID_PAYLOAD)
    with patch("app.services.transcripts.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = fake
        yield mock_get_client


@pytest.mark.unit
def test_analyze_transcripts_returns_all_13_keys(_mock_llm):
    from app.services.transcripts import analyze_transcripts

    result = analyze_transcripts(["transcript one", "transcript two"])

    assert set(result.keys()) == set(STYLE_FIELDS)


@pytest.mark.unit
def test_analyze_transcripts_values_match_payload(_mock_llm):
    from app.services.transcripts import analyze_transcripts

    result = analyze_transcripts(["some transcript"])

    for field in STYLE_FIELDS:
        assert result[field] == f"value_{field}"


@pytest.mark.unit
def test_analyze_transcripts_invalid_json_raises():
    bad = MagicMock()
    bad.choices[0].message.content = "not valid json {{{"
    bad.usage.prompt_tokens = 1
    bad.usage.completion_tokens = 1
    bad.usage.total_tokens = 2

    with patch("app.services.transcripts.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = bad
        from app.services.transcripts import analyze_transcripts

        with pytest.raises(json.JSONDecodeError):
            analyze_transcripts(["some transcript"])


@pytest.mark.unit
def test_analyze_transcripts_missing_key_raises(mock_llm_response):
    empty = mock_llm_response({})

    with patch("app.services.transcripts.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = empty
        from app.services.transcripts import analyze_transcripts

        with pytest.raises(KeyError):
            analyze_transcripts(["some transcript"])

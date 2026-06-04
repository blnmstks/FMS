import json
import random
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def _mock_deps(mock_llm_response, valid_branding_payload):
    """Patch get_client and encode_images so no real I/O happens."""
    fake_response = mock_llm_response(valid_branding_payload)
    with (
        patch("app.services.branding.get_client") as mock_get_client,
        patch("app.services.branding.encode_images", return_value=[]),
    ):
        mock_get_client.return_value.chat.completions.create.return_value = fake_response
        yield mock_get_client


@pytest.mark.unit
def test_analyze_channel_returns_required_keys(_mock_deps):
    from app.services.branding import analyze_channel

    result = analyze_channel("TestChannel", ["fake/path.png"])

    assert set(result.keys()) == {
        "channel_name",
        "channel_description",
        "channel_avatar",
        "channel_banner",
        "channel_info_complete",
    }


@pytest.mark.unit
def test_analyze_channel_info_complete_is_true(_mock_deps):
    from app.services.branding import analyze_channel

    result = analyze_channel("TestChannel", ["fake/path.png"])
    assert result["channel_info_complete"] is True


@pytest.mark.unit
def test_analyze_channel_values_from_payload(_mock_deps, valid_branding_payload):
    from app.services.branding import analyze_channel

    random.seed(0)
    result = analyze_channel("TestChannel", ["fake/path.png"])

    assert result["channel_name"] in valid_branding_payload["channel_name_variants"]
    assert result["channel_description"] in valid_branding_payload["channel_description_variants"]
    assert result["channel_avatar"] == valid_branding_payload["channel_avatar_prompt"]
    assert result["channel_banner"] == valid_branding_payload["channel_banner_prompt"]


@pytest.mark.unit
def test_analyze_channel_invalid_json_raises(mock_llm_response):
    bad_response = MagicMock()
    bad_response.choices[0].message.content = "not valid json {{{"
    bad_response.usage.prompt_tokens = 1
    bad_response.usage.completion_tokens = 1
    bad_response.usage.total_tokens = 2

    with (
        patch("app.services.branding.get_client") as mock_get_client,
        patch("app.services.branding.encode_images", return_value=[]),
    ):
        mock_get_client.return_value.chat.completions.create.return_value = bad_response
        from app.services.branding import analyze_channel
        with pytest.raises(json.JSONDecodeError):
            analyze_channel("TestChannel", ["fake/path.png"])


@pytest.mark.unit
def test_analyze_channel_missing_key_raises(mock_llm_response):
    empty_response = mock_llm_response({})

    with (
        patch("app.services.branding.get_client") as mock_get_client,
        patch("app.services.branding.encode_images", return_value=[]),
    ):
        mock_get_client.return_value.chat.completions.create.return_value = empty_response
        from app.services.branding import analyze_channel
        with pytest.raises(KeyError):
            analyze_channel("TestChannel", ["fake/path.png"])

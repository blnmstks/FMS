from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
def test_synthesize_calls_generate_content_with_audio_config_and_returns_bytes():
    from app.infrastructure import google_tts_client as client_mod

    resp = MagicMock()
    resp.candidates[0].content.parts[0].inline_data.data = b"PCMDATA"
    client = MagicMock()
    client.models.generate_content.return_value = resp

    with patch.object(client_mod, "get_client", return_value=client):
        result = client_mod.synthesize("PROMPT", "Charon", "gemini-3.1-flash-tts-preview")

    assert result == b"PCMDATA"

    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-3.1-flash-tts-preview"
    assert kwargs["contents"] == "PROMPT"

    config = kwargs["config"]
    assert list(config.response_modalities) == ["AUDIO"]
    assert config.speech_config.voice_config.prebuilt_voice_config.voice_name == "Charon"


@pytest.mark.unit
def test_get_client_uses_api_key():
    from app.infrastructure import google_tts_client as client_mod

    with patch.object(client_mod.genai, "Client") as mock_client:
        client_mod.get_client()

    _, kwargs = mock_client.call_args
    assert "api_key" in kwargs

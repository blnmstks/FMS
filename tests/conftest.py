import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_llm_response():
    """Returns a factory for fake LLM chat completion responses."""
    def _make(content: dict):
        response = MagicMock()
        response.choices[0].message.content = json.dumps(content)
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 5
        response.usage.total_tokens = 15
        return response
    return _make


@pytest.fixture
def valid_branding_payload():
    return {
        "channel_name_variants": ["Alpha Channel", "Beta Channel"],
        "channel_description_variants": ["Short desc.", "Long desc."],
        "channel_avatar_prompt": "A minimalist logo with dark background",
        "channel_banner_prompt": "Wide cinematic banner with blue tones",
    }


@pytest.fixture
def mock_psycopg_connect():
    """Patch psycopg.connect for db.py unit tests."""
    with patch("app.db.psycopg.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_connect, mock_conn, mock_cursor

import json

import pytest

from app.db import STYLE_FIELDS

FULL_ROW = ("MyChannel", "A great channel", "https://avatar.png", "https://banner.png")
FULL_STYLE_ROW = tuple(f"val_{f}" for f in STYLE_FIELDS) + (json.dumps(["note1.md"]),)
EXPECTED_FULL = {
    "channel_name": "MyChannel",
    "channel_description": "A great channel",
    "channel_avatar": "https://avatar.png",
    "channel_banner": "https://banner.png",
    "channel_info_complete": True,
}


@pytest.mark.unit
def test_fetch_returns_full_dict_when_row_exists(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = FULL_ROW

    from app.db import fetch_channel_info

    result = fetch_channel_info()

    assert result == EXPECTED_FULL


@pytest.mark.unit
def test_fetch_returns_incomplete_when_no_row(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = None

    from app.db import fetch_channel_info

    result = fetch_channel_info()

    assert result == {"channel_info_complete": False}


@pytest.mark.unit
def test_fetch_returns_incomplete_when_partial_nulls(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = (
        "MyChannel",
        None,
        "https://avatar.png",
        "https://banner.png",
    )

    from app.db import fetch_channel_info

    result = fetch_channel_info()

    assert result == {"channel_info_complete": False}


@pytest.mark.unit
def test_upsert_calls_update_when_row_exists(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = (1,)

    from app.db import upsert_channel_info

    upsert_channel_info(EXPECTED_FULL)

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("UPDATE" in c for c in calls)
    assert not any("INSERT" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_upsert_calls_insert_when_no_row(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = None

    from app.db import upsert_channel_info

    upsert_channel_info(EXPECTED_FULL)

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("INSERT" in c for c in calls)
    assert not any("UPDATE" in c for c in calls)
    mock_conn.commit.assert_called_once()


# --- fetch_channel_style_info ---


@pytest.mark.unit
def test_fetch_style_returns_full_dict_when_all_filled(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = FULL_STYLE_ROW

    from app.db import fetch_channel_style_info

    result = fetch_channel_style_info()

    assert result["channel_style_complete"] is True
    for field in STYLE_FIELDS:
        assert field in result
    assert result["transcript_files"] == ["note1.md"]


@pytest.mark.unit
def test_fetch_style_returns_incomplete_when_no_row(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = None

    from app.db import fetch_channel_style_info

    result = fetch_channel_style_info()

    assert result == {"channel_style_complete": False}


@pytest.mark.unit
def test_fetch_style_returns_incomplete_when_one_field_null(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    row_with_null = ("val",) * (len(STYLE_FIELDS) - 1) + (None,) + (None,)
    mock_cursor.fetchone.return_value = row_with_null

    from app.db import fetch_channel_style_info

    result = fetch_channel_style_info()

    assert result == {"channel_style_complete": False}


@pytest.mark.unit
def test_fetch_style_returns_incomplete_when_one_field_empty(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    row_with_empty = ("val",) * (len(STYLE_FIELDS) - 1) + ("",) + (None,)
    mock_cursor.fetchone.return_value = row_with_empty

    from app.db import fetch_channel_style_info

    result = fetch_channel_style_info()

    assert result == {"channel_style_complete": False}


@pytest.mark.unit
def test_fetch_style_transcript_files_defaults_to_empty_list(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    row_no_files = tuple(f"val_{f}" for f in STYLE_FIELDS) + (None,)
    mock_cursor.fetchone.return_value = row_no_files

    from app.db import fetch_channel_style_info

    result = fetch_channel_style_info()

    assert result["transcript_files"] == []


# --- upsert_channel_style_info ---


@pytest.mark.unit
def test_upsert_style_calls_update_when_row_exists(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = (1,)

    from app.db import upsert_channel_style_info

    style = {f: f"val_{f}" for f in STYLE_FIELDS}
    upsert_channel_style_info(style, ["note1.md"])

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("UPDATE" in c for c in calls)
    assert not any("INSERT" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_upsert_style_calls_insert_when_no_row(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = None

    from app.db import upsert_channel_style_info

    style = {f: f"val_{f}" for f in STYLE_FIELDS}
    upsert_channel_style_info(style, [])

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("INSERT" in c for c in calls)
    assert not any("UPDATE" in c for c in calls)
    mock_conn.commit.assert_called_once()

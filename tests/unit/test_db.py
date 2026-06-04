import pytest

FULL_ROW = ("MyChannel", "A great channel", "https://avatar.png", "https://banner.png")
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
    mock_cursor.fetchone.return_value = ("MyChannel", None, "https://avatar.png", "https://banner.png")

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

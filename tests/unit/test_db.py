import json

import pytest

from app.db import IDEAS_STATUSES, STYLE_FIELDS

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


# --- migrate_ideas_table ---


@pytest.mark.unit
def test_migrate_ideas_table_creates_enum_and_table(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import migrate_ideas_table

    migrate_ideas_table()

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("idea_status" in c for c in calls)
    assert any("CREATE TABLE IF NOT EXISTS ideas" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_migrate_ideas_table_enum_contains_all_statuses(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import migrate_ideas_table

    migrate_ideas_table()

    create_type_call = next(
        str(c)
        for c in mock_cursor.execute.call_args_list
        if "idea_status" in str(c) and "ideas" not in str(c)
    )
    for status in IDEAS_STATUSES:
        assert status in create_type_call


@pytest.mark.unit
def test_migrate_ideas_table_alters_type_for_each_status(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import migrate_ideas_table

    migrate_ideas_table()

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("ALTER TYPE idea_status ADD VALUE IF NOT EXISTS" in c for c in calls)
    for status in IDEAS_STATUSES:
        assert any(
            "ALTER TYPE idea_status ADD VALUE IF NOT EXISTS" in c and status in c for c in calls
        )


@pytest.mark.unit
def test_migrate_ideas_table_includes_raw_idea_status():
    assert "raw_idea" in IDEAS_STATUSES


# --- fetch_raw_idea ---


@pytest.mark.unit
def test_fetch_raw_idea_returns_idea_when_exists(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = (7, "My Idea")

    from app.db import fetch_raw_idea

    result = fetch_raw_idea()

    assert result == {"idea_id": 7, "idea_name": "My Idea", "raw_idea_exists": True}


@pytest.mark.unit
def test_fetch_raw_idea_returns_false_when_no_row(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = None

    from app.db import fetch_raw_idea

    result = fetch_raw_idea()

    assert result == {"raw_idea_exists": False}


# --- fetch_idea_by_status ---


@pytest.mark.unit
def test_fetch_idea_by_status_returns_idea_when_exists(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = (7, "X")

    from app.db import fetch_idea_by_status

    result = fetch_idea_by_status("scenario_finished")

    assert result == {"idea_id": 7, "idea_name": "X", "exists": True}


@pytest.mark.unit
def test_fetch_idea_by_status_returns_false_when_no_row(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = None

    from app.db import fetch_idea_by_status

    result = fetch_idea_by_status("scenario_finished")

    assert result == {"exists": False}


@pytest.mark.unit
def test_fetch_idea_by_status_passes_status_as_param(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = (1, "Y")

    from app.db import fetch_idea_by_status

    fetch_idea_by_status("audio_generated")

    select_call = next(
        c for c in mock_cursor.execute.call_args_list if "SELECT id, name FROM ideas" in str(c)
    )
    assert select_call.args[1] == ("audio_generated",)


# --- fetch_present_idea_statuses ---


@pytest.mark.unit
def test_fetch_present_idea_statuses_returns_distinct_list(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchall.return_value = [("raw_idea",), ("scenario_finished",)]

    from app.db import fetch_present_idea_statuses

    result = fetch_present_idea_statuses()

    assert result == ["raw_idea", "scenario_finished"]


@pytest.mark.unit
def test_fetch_present_idea_statuses_empty_when_no_rows(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchall.return_value = []

    from app.db import fetch_present_idea_statuses

    assert fetch_present_idea_statuses() == []


# --- insert_idea ---


@pytest.mark.unit
def test_insert_idea_executes_insert_and_commits(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import insert_idea

    insert_idea("Some Idea", "raw_idea")

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("INSERT INTO ideas" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_insert_idea_passes_name_and_status_as_params(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import insert_idea

    insert_idea("Some Idea", "raw_idea")

    insert_call = next(
        c for c in mock_cursor.execute.call_args_list if "INSERT INTO ideas" in str(c)
    )
    assert insert_call.args[1] == ("Some Idea", "raw_idea")


# --- update_idea_status ---


@pytest.mark.unit
def test_update_idea_status_executes_update_and_commits(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import update_idea_status

    update_idea_status(7, "scenario_finished")

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("UPDATE ideas" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_update_idea_status_passes_status_and_id_as_params(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import update_idea_status

    update_idea_status(7, "scenario_finished")

    update_call = next(c for c in mock_cursor.execute.call_args_list if "UPDATE ideas" in str(c))
    assert update_call.args[1] == ("scenario_finished", 7)


# --- migrate_scenarios_table ---


@pytest.mark.unit
def test_migrate_scenarios_table_creates_table_with_fk(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import migrate_scenarios_table

    migrate_scenarios_table()

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("CREATE TABLE IF NOT EXISTS scenarios" in c for c in calls)
    assert any("REFERENCES ideas" in c for c in calls)
    mock_conn.commit.assert_called_once()


# --- insert_scenario ---


@pytest.mark.unit
def test_insert_scenario_executes_insert_and_commits(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import insert_scenario

    insert_scenario("Some scenario text", 7)

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("INSERT INTO scenarios" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_insert_scenario_passes_scenario_and_idea_as_params(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import insert_scenario

    insert_scenario("Some scenario text", 7)

    insert_call = next(
        c for c in mock_cursor.execute.call_args_list if "INSERT INTO scenarios" in str(c)
    )
    assert insert_call.args[1] == ("Some scenario text", 7)

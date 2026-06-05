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


# --- migrate_channel_info_table ---


@pytest.mark.unit
def test_migrate_channel_info_table_creates_table(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import migrate_channel_info_table

    migrate_channel_info_table()

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("CREATE TABLE IF NOT EXISTS channel_info" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_migrate_channel_info_table_includes_base_columns(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import migrate_channel_info_table

    migrate_channel_info_table()

    create_call = next(
        str(c)
        for c in mock_cursor.execute.call_args_list
        if "CREATE TABLE IF NOT EXISTS channel_info" in str(c)
    )
    for col in ("name", "description", "avatar", "banner"):
        assert col in create_call


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


# --- migrate_visual_styles_table ---


@pytest.mark.unit
def test_migrate_visual_styles_table_creates_table_with_fk(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import migrate_visual_styles_table

    migrate_visual_styles_table()

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("CREATE TABLE IF NOT EXISTS visual_styles" in c for c in calls)
    assert any("REFERENCES channel_info" in c for c in calls)
    assert any("REFERENCES ideas" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_migrate_visual_styles_table_has_idea_column(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import migrate_visual_styles_table

    migrate_visual_styles_table()

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("idea" in c and "REFERENCES ideas" in c for c in calls)


@pytest.mark.unit
def test_migrate_visual_styles_table_includes_all_style_fields(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import VISUAL_STYLE_FIELDS, migrate_visual_styles_table

    migrate_visual_styles_table()

    create_call = next(
        str(c)
        for c in mock_cursor.execute.call_args_list
        if "CREATE TABLE IF NOT EXISTS visual_styles" in str(c)
    )
    for field in VISUAL_STYLE_FIELDS:
        assert field in create_call


# --- upsert_visual_styles ---


@pytest.mark.unit
def test_upsert_visual_styles_calls_update_when_row_exists(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = (1,)

    from app.db import VISUAL_STYLE_FIELDS, upsert_visual_styles

    style = {f: f"val_{f}" for f in VISUAL_STYLE_FIELDS}
    upsert_visual_styles(style, 5)

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("UPDATE visual_styles" in c for c in calls)
    assert not any("INSERT INTO visual_styles" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_upsert_visual_styles_calls_insert_when_no_row(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = None

    from app.db import VISUAL_STYLE_FIELDS, upsert_visual_styles

    style = {f: f"val_{f}" for f in VISUAL_STYLE_FIELDS}
    upsert_visual_styles(style, 5)

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("INSERT INTO visual_styles" in c for c in calls)
    assert not any("UPDATE visual_styles" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_upsert_visual_styles_lookup_by_idea(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = None

    from app.db import VISUAL_STYLE_FIELDS, upsert_visual_styles

    style = {f: f"val_{f}" for f in VISUAL_STYLE_FIELDS}
    upsert_visual_styles(style, 5)

    select_call = next(
        c for c in mock_cursor.execute.call_args_list if "SELECT id FROM visual_styles" in str(c)
    )
    assert "WHERE idea" in str(select_call)
    assert select_call.args[1] == (5,)


# --- fetch_rows ---


@pytest.mark.unit
def test_fetch_rows_maps_columns_to_dicts(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.description = [("id",), ("channel_info",)]
    mock_cursor.fetchall.return_value = [(1, "5")]

    from app.db import fetch_rows

    result = fetch_rows("visual_styles", "channel_info", 5)

    assert result == [{"id": 1, "channel_info": "5"}]


@pytest.mark.unit
def test_fetch_rows_returns_empty_list_when_no_rows(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.description = [("id",), ("channel_info",)]
    mock_cursor.fetchall.return_value = []

    from app.db import fetch_rows

    assert fetch_rows("visual_styles", "channel_info", 5) == []


@pytest.mark.unit
def test_fetch_rows_passes_value_as_param(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.description = [("id",)]
    mock_cursor.fetchall.return_value = []

    from app.db import fetch_rows

    fetch_rows("scenarios", "idea", 7)

    select_call = next(
        c for c in mock_cursor.execute.call_args_list if "SELECT * FROM scenarios" in str(c)
    )
    assert select_call.args[1] == (7,)


# --- fetch_row_by_id ---


@pytest.mark.unit
def test_fetch_row_by_id_returns_dict_when_exists(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.description = [("id",), ("name",)]
    mock_cursor.fetchone.return_value = (7, "X")

    from app.db import fetch_row_by_id

    result = fetch_row_by_id("ideas", 7)

    assert result == {"id": 7, "name": "X"}


@pytest.mark.unit
def test_fetch_row_by_id_returns_none_when_no_row(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    mock_cursor.fetchone.return_value = None

    from app.db import fetch_row_by_id

    assert fetch_row_by_id("ideas", 7) is None


# --- fetch_related ---


@pytest.mark.unit
def test_fetch_related_collects_children_for_parent_source(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    # channel_info — источник-родитель: у него нет FK-рёбер вверх, только дети (visual_styles).
    # fetch_row_by_id(channel_info) -> строка канала; fetch_rows(visual_styles) -> список.
    mock_cursor.description = [("id",)]
    mock_cursor.fetchone.return_value = (1,)
    mock_cursor.fetchall.return_value = [(10, "1"), (11, "1")]

    from app.db import fetch_related

    result = fetch_related("channel_info", 1)

    assert result["source"] == {"id": 1}
    assert isinstance(result["children"]["visual_styles"], list)
    assert len(result["children"]["visual_styles"]) == 2
    assert result["parents"] == {}


@pytest.mark.unit
def test_fetch_related_collects_parent_for_child_source(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect
    # scenarios — источник-потомок (ребро scenarios→ideas) и одновременно родитель для
    # characters_sheet и image_prompts (рёбра ...→scenarios).
    # fetch_row_by_id: сценарий с idea=7, затем строка идеи; fetch_rows(children) → [].
    mock_cursor.description = [("id",), ("scenario",), ("idea",)]
    mock_cursor.fetchone.side_effect = [(5, "text", 7), (7, "name", "raw_idea")]
    mock_cursor.fetchall.return_value = []

    from app.db import fetch_related

    result = fetch_related("scenarios", 5)

    assert result["source"]["idea"] == 7
    assert result["parents"]["ideas"]["id"] == 7
    assert result["children"] == {"characters_sheet": [], "image_prompts": []}


# --- migrate_characters_sheet_table ---


@pytest.mark.unit
def test_migrate_characters_sheet_table_creates_table(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import migrate_characters_sheet_table

    migrate_characters_sheet_table()

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("CREATE TABLE IF NOT EXISTS characters_sheet" in c for c in calls)
    assert any("JSONB" in c for c in calls)
    assert any("REFERENCES scenarios" in c for c in calls)
    mock_conn.commit.assert_called_once()


# --- insert_characters ---


def _sample_characters():
    return [
        {
            "label": "Jack",
            "face": {"hair": "black"},
            "build": "tall",
            "outfit": {"item_1": {"color": "red"}},
            "baseline_neutral_expression": "calm",
        },
        {
            "label": "Anna",
            "face": {"hair": "blonde"},
            "build": "short",
            "outfit": {"item_1": {"color": "blue"}},
            "baseline_neutral_expression": "stern",
        },
    ]


@pytest.mark.unit
def test_insert_characters_deletes_then_inserts(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import insert_characters

    insert_characters(_sample_characters(), 3)

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert sum("DELETE FROM characters_sheet" in c for c in calls) == 1
    assert sum("INSERT INTO characters_sheet" in c for c in calls) == 2
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_insert_characters_maps_label_and_scenario(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import insert_characters

    insert_characters(_sample_characters(), 3)

    insert_call = next(
        c for c in mock_cursor.execute.call_args_list if "INSERT INTO characters_sheet" in str(c)
    )
    params = insert_call.args[1]
    assert params[0] == "Jack"
    assert params[-1] == 3


@pytest.mark.unit
def test_insert_characters_empty_list_only_deletes(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import insert_characters

    insert_characters([], 3)

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("DELETE FROM characters_sheet" in c for c in calls)
    assert not any("INSERT INTO characters_sheet" in c for c in calls)
    mock_conn.commit.assert_called_once()


# --- migrate_image_prompts_table ---


@pytest.mark.unit
def test_migrate_image_prompts_table_creates_table_with_fk(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import migrate_image_prompts_table

    migrate_image_prompts_table()

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("CREATE TABLE IF NOT EXISTS image_prompts" in c for c in calls)
    assert any("REFERENCES scenarios" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_migrate_image_prompts_table_includes_all_fields(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import IMAGE_PROMPT_FIELDS, migrate_image_prompts_table

    migrate_image_prompts_table()

    create_call = next(
        str(c)
        for c in mock_cursor.execute.call_args_list
        if "CREATE TABLE IF NOT EXISTS image_prompts" in str(c)
    )
    for field in IMAGE_PROMPT_FIELDS:
        assert field in create_call


# --- insert_image_prompt ---


@pytest.mark.unit
def test_insert_image_prompt_executes_insert_and_commits(mock_psycopg_connect):
    _, mock_conn, mock_cursor = mock_psycopg_connect

    from app.db import IMAGE_PROMPT_FIELDS, insert_image_prompt

    prompt = {f: f"val_{f}" for f in IMAGE_PROMPT_FIELDS}
    insert_image_prompt(prompt, 3)

    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("INSERT INTO image_prompts" in c for c in calls)
    mock_conn.commit.assert_called_once()


@pytest.mark.unit
def test_insert_image_prompt_last_param_is_scenario_id(mock_psycopg_connect):
    _, _, mock_cursor = mock_psycopg_connect

    from app.db import IMAGE_PROMPT_FIELDS, insert_image_prompt

    prompt = {f: f"val_{f}" for f in IMAGE_PROMPT_FIELDS}
    insert_image_prompt(prompt, 3)

    insert_call = next(
        c for c in mock_cursor.execute.call_args_list if "INSERT INTO image_prompts" in str(c)
    )
    assert insert_call.args[1][-1] == 3

from unittest.mock import patch

import pytest
from langgraph.graph import END

from app.db import IMAGE_PROMPT_FIELDS, VISUAL_STYLE_FIELDS
from app.graph import (
    _make_stub,
    _route_dispatch,
    _route_s1,
    _route_s4,
    dispatch,
    s5_scenario,
    s6_visual_style,
    s7_image_prompt,
    s8_generate_image,
    s9_audio_prompts,
    select_target_step,
)

# --- _route_s1 ---


@pytest.mark.unit
def test_route_s1_goes_to_s2_when_screenshots():
    assert _route_s1({"use_screenshots": True}) == "s2"


@pytest.mark.unit
def test_route_s1_goes_to_s3_when_manual():
    assert _route_s1({"use_screenshots": False}) == "s3"


@pytest.mark.unit
def test_route_s1_goes_to_s3_when_flag_absent():
    assert _route_s1({}) == "s3"


# --- _route_s4 ---


@pytest.mark.unit
def test_route_s4_goes_to_pick_when_ideas_generated():
    assert _route_s4({"generated_ideas": ["a", "b"]}) == "s4_pick"


@pytest.mark.unit
def test_route_s4_goes_to_dispatch_when_no_generated_ideas():
    assert _route_s4({}) == "dispatch"


# --- select_target_step ---


@pytest.mark.unit
def test_select_target_step_own_status():
    assert select_target_step({"raw_idea"}, 5) == 5
    assert select_target_step({"scenario_finished"}, 6) == 6


@pytest.mark.unit
def test_select_target_step_own_status_takes_priority():
    assert select_target_step({"raw_idea", "audio_generated"}, 5) == 5


@pytest.mark.unit
def test_select_target_step_earliest_previous():
    # своего (9) нет, предыдущие 6 и 7 → самый ранний 6
    assert select_target_step({"scenario_finished", "clips_visual_style_finished"}, 9) == 6


@pytest.mark.unit
def test_select_target_step_previous_when_no_own():
    assert select_target_step({"raw_idea"}, 8) == 5


@pytest.mark.unit
def test_select_target_step_nearest_following():
    assert select_target_step({"audio_generated"}, 5) == 11


@pytest.mark.unit
def test_select_target_step_image_generated_targets_step_nine():
    # «yes»-ветка шага 7 выставляет image_generated → шаг 9 (минуя шаг 8).
    assert select_target_step({"image_generated"}, 8) == 9


@pytest.mark.unit
def test_select_target_step_no_ideas_returns_four():
    assert select_target_step(set(), 5) == 4


# --- dispatch node ---


@pytest.mark.unit
def test_dispatch_targets_step_for_present_status():
    with patch("app.graph.fetch_present_idea_statuses", return_value=["raw_idea"]):
        assert dispatch({})["pipeline_target"] == 5


@pytest.mark.unit
def test_dispatch_uses_pipeline_step_cursor():
    with patch("app.graph.fetch_present_idea_statuses", return_value=["scenario_finished"]):
        assert dispatch({"pipeline_step": 6})["pipeline_target"] == 6


@pytest.mark.unit
def test_dispatch_targets_four_when_no_ideas():
    with patch("app.graph.fetch_present_idea_statuses", return_value=[]):
        assert dispatch({})["pipeline_target"] == 4


# --- _route_dispatch ---


@pytest.mark.unit
def test_route_dispatch_goes_to_target_step():
    assert _route_dispatch({"pipeline_target": 5}) == "s5"


@pytest.mark.unit
def test_route_dispatch_goes_to_s4_when_target_four():
    assert _route_dispatch({"pipeline_target": 4}) == "s4"


@pytest.mark.unit
def test_route_dispatch_ends_when_target_already_executed():
    assert _route_dispatch({"pipeline_target": 6, "executed_steps": [6]}) == END


@pytest.mark.unit
def test_route_dispatch_goes_to_target_when_not_yet_executed():
    assert _route_dispatch({"pipeline_target": 7, "executed_steps": [5, 6]}) == "s7"


# --- s5_scenario ---


@pytest.mark.unit
def test_s5_scenario_generates_saves_and_advances_idea():
    idea = {"idea_id": 7, "idea_name": "X", "raw_idea_exists": True}
    with (
        patch("app.graph.fetch_raw_idea", return_value=idea),
        patch(
            "app.graph.fetch_channel_info",
            return_value={"channel_name": "C", "channel_description": "D"},
        ),
        patch("app.graph.fetch_channel_style_info", return_value={"transcript_files": []}),
        patch("app.graph.generate_scenario", return_value="SCENARIO") as gen,
        patch("app.graph.insert_scenario") as ins,
        patch("app.graph.update_idea_status") as upd,
    ):
        result = s5_scenario({})

    gen.assert_called_once()
    ins.assert_called_once_with("SCENARIO", 7)
    upd.assert_called_once_with(7, "scenario_finished")
    assert result["pipeline_step"] == 6
    assert 5 in result["executed_steps"]


@pytest.mark.unit
def test_s5_scenario_advances_without_work_when_no_idea():
    with patch("app.graph.fetch_raw_idea", return_value={"raw_idea_exists": False}):
        with patch("app.graph.generate_scenario") as gen:
            result = s5_scenario({})

    gen.assert_not_called()
    assert result["pipeline_step"] == 6
    assert 5 in result["executed_steps"]


# --- s6_visual_style ---


@pytest.mark.unit
def test_s6_visual_style_generates_saves_and_advances():
    idea = {"idea_id": 7, "idea_name": "X", "exists": True}
    profile = {f: f"val_{f}" for f in VISUAL_STYLE_FIELDS}
    profile["characters"] = [{"label": "Jack"}]
    with (
        patch("app.graph.fetch_idea_by_status", return_value=idea),
        patch("app.graph.fetch_rows", return_value=[{"id": 3, "scenario": "SCEN"}]),
        patch("app.graph.interrupt", return_value="a.jpg, b.jpg"),
        patch("app.graph.fetch_channel_style_info", return_value={}),
        patch("app.graph.generate_visual_style", return_value=profile) as gen,
        patch("app.graph.upsert_visual_styles") as ups,
        patch("app.graph.insert_characters") as ins_chars,
        patch("app.graph.update_idea_status") as upd,
    ):
        result = s6_visual_style({})

    gen.assert_called_once()
    expected_style = {f: f"val_{f}" for f in VISUAL_STYLE_FIELDS}
    ups.assert_called_once_with(expected_style, 7)
    ins_chars.assert_called_once_with(profile["characters"], 3)
    upd.assert_called_once_with(7, "clips_visual_style_finished")
    assert result["pipeline_step"] == 7
    assert 6 in result["executed_steps"]


@pytest.mark.unit
def test_s6_visual_style_advances_without_work_when_no_idea():
    with (
        patch("app.graph.fetch_idea_by_status", return_value={"exists": False}),
        patch("app.graph.generate_visual_style") as gen,
        patch("app.graph.insert_characters") as ins_chars,
        patch("app.graph.interrupt") as itr,
    ):
        result = s6_visual_style({})

    gen.assert_not_called()
    ins_chars.assert_not_called()
    itr.assert_not_called()
    assert result["pipeline_step"] == 7
    assert 6 in result["executed_steps"]


# --- s7_image_prompt ---


def _fetch_rows_for_s7(table, column, value):
    return {
        "scenarios": [{"id": 3, "scenario": "SCEN"}],
        "visual_styles": [{f: f"vs_{f}" for f in VISUAL_STYLE_FIELDS}],
        "characters_sheet": [{"label": "Jack"}],
    }[table]


@pytest.mark.unit
def test_s7_image_prompt_no_branch_generates_saves_and_advances():
    idea = {"idea_id": 7, "idea_name": "X", "exists": True}
    prompt = {f: f"val_{f}" for f in IMAGE_PROMPT_FIELDS}
    with (
        patch("app.graph.fetch_idea_by_status", return_value=idea),
        patch("app.graph.interrupt", return_value="n"),
        patch("app.graph.fetch_rows", side_effect=_fetch_rows_for_s7),
        patch("app.graph.generate_image_prompt", return_value=prompt) as gen,
        patch("app.graph.insert_image_prompt") as ins,
        patch("app.graph.update_idea_status") as upd,
    ):
        result = s7_image_prompt({})

    gen.assert_called_once()
    expected_style = {f: f"vs_{f}" for f in VISUAL_STYLE_FIELDS}
    assert gen.call_args.args == ("SCEN", expected_style, [{"label": "Jack"}])
    ins.assert_called_once_with(prompt, 3)
    upd.assert_called_once_with(7, "image_prompt_finished")
    assert result["pipeline_step"] == 8
    assert 7 in result["executed_steps"]


@pytest.mark.unit
def test_s7_image_prompt_yes_branch_skips_to_step_nine():
    # «yes»: картинка уже есть — генерации/записи нет, статус → image_generated (минуя шаг 8).
    idea = {"idea_id": 7, "idea_name": "X", "exists": True}
    with (
        patch("app.graph.fetch_idea_by_status", return_value=idea),
        patch("app.graph.interrupt", return_value="y"),
        patch("app.graph.generate_image_prompt") as gen,
        patch("app.graph.insert_image_prompt") as ins,
        patch("app.graph.update_idea_status") as upd,
    ):
        result = s7_image_prompt({})

    gen.assert_not_called()
    ins.assert_not_called()
    upd.assert_called_once_with(7, "image_generated")
    assert result["pipeline_step"] == 8
    assert 7 in result["executed_steps"]


@pytest.mark.unit
def test_s7_image_prompt_advances_without_work_when_no_idea():
    with (
        patch("app.graph.fetch_idea_by_status", return_value={"exists": False}),
        patch("app.graph.interrupt") as itr,
        patch("app.graph.generate_image_prompt") as gen,
        patch("app.graph.insert_image_prompt") as ins,
    ):
        result = s7_image_prompt({})

    itr.assert_not_called()
    gen.assert_not_called()
    ins.assert_not_called()
    assert result["pipeline_step"] == 8
    assert 7 in result["executed_steps"]


# --- s8_generate_image ---


def _fetch_rows_for_s8(table, column, value):
    return {
        "scenarios": [{"id": 3, "scenario": "SCEN"}],
        "image_prompts": [{"id": 9, **{f: f"v_{f}" for f in IMAGE_PROMPT_FIELDS}}],
    }[table]


@pytest.mark.unit
def test_s8_generate_image_generates_registers_and_advances():
    idea = {"idea_id": 7, "idea_name": "X", "exists": True}
    with (
        patch("app.graph.fetch_idea_by_status", return_value=idea),
        patch("app.graph.fetch_rows", side_effect=_fetch_rows_for_s8),
        patch("app.graph.generate_first_beat_image", return_value="assets/images/x.png") as gen,
        patch("app.graph.insert_image") as ins,
        patch("app.graph.update_idea_status") as upd,
    ):
        result = s8_generate_image({})

    gen.assert_called_once()
    image_prompt_row = {"id": 9, **{f: f"v_{f}" for f in IMAGE_PROMPT_FIELDS}}
    assert gen.call_args.args == (image_prompt_row, 7)
    ins.assert_called_once_with("local", "assets/images/x.png", "first_beat", 9)
    upd.assert_called_once_with(7, "image_generated")
    assert result["pipeline_step"] == 9
    assert 8 in result["executed_steps"]


@pytest.mark.unit
def test_s8_generate_image_advances_without_work_when_no_idea():
    with (
        patch("app.graph.fetch_idea_by_status", return_value={"exists": False}),
        patch("app.graph.generate_first_beat_image") as gen,
        patch("app.graph.insert_image") as ins,
    ):
        result = s8_generate_image({})

    gen.assert_not_called()
    ins.assert_not_called()
    assert result["pipeline_step"] == 9
    assert 8 in result["executed_steps"]


@pytest.mark.unit
def test_s8_generate_image_skips_when_no_image_prompt():
    idea = {"idea_id": 7, "idea_name": "X", "exists": True}
    with (
        patch("app.graph.fetch_idea_by_status", return_value=idea),
        patch("app.graph.fetch_rows", return_value=[]),  # ни scenario, ни image_prompt
        patch("app.graph.generate_first_beat_image") as gen,
        patch("app.graph.insert_image") as ins,
        patch("app.graph.update_idea_status") as upd,
    ):
        result = s8_generate_image({})

    gen.assert_not_called()
    ins.assert_not_called()
    upd.assert_not_called()
    assert result["pipeline_step"] == 9
    assert 8 in result["executed_steps"]


# --- s9_audio_prompts ---


def _fetch_rows_for_s9(table, column, value):
    return {
        "scenarios": [{"id": 3, "scenario": "SCEN"}],
        "audio_seg_prompts": [{"seg_id": 11, "speaker": "Narrator"}],
    }[table]


def _fetch_rows_for_s9_no_existing(table, column, value):
    return {
        "scenarios": [{"id": 3, "scenario": "SCEN"}],
        "audio_seg_prompts": [],
    }[table]


_AUDIO_RESULT = {
    "audio_segments": [{"seg_id": 1, "speaker": "N", "tts_text": "Hi.", "beat_ids": [1]}],
    "beats": [{"id": 1, "seg_id": 1, "audio_text": "Hi."}],
}


@pytest.mark.unit
def test_s9_audio_prompts_existing_continue_advances_without_generating():
    idea = {"idea_id": 7, "idea_name": "X", "exists": True}
    with (
        patch("app.graph.fetch_idea_by_status", return_value=idea),
        patch("app.graph.fetch_rows", side_effect=_fetch_rows_for_s9),
        patch("app.graph.interrupt", return_value="1"),
        patch("app.graph.generate_audio_prompts") as gen,
        patch("app.graph.replace_audio_prompts") as rep,
        patch("app.graph.update_idea_status") as upd,
    ):
        result = s9_audio_prompts({})

    gen.assert_not_called()
    rep.assert_not_called()
    upd.assert_called_once_with(7, "audio_prompts_finished")
    assert result["pipeline_step"] == 10
    assert 9 in result["executed_steps"]


@pytest.mark.unit
def test_s9_audio_prompts_existing_regenerate_replaces_and_advances():
    idea = {"idea_id": 7, "idea_name": "X", "exists": True}
    with (
        patch("app.graph.fetch_idea_by_status", return_value=idea),
        patch("app.graph.fetch_rows", side_effect=_fetch_rows_for_s9),
        patch("app.graph.interrupt", return_value="2"),
        patch("app.graph.generate_audio_prompts", return_value=_AUDIO_RESULT) as gen,
        patch("app.graph.replace_audio_prompts") as rep,
        patch("app.graph.update_idea_status") as upd,
    ):
        result = s9_audio_prompts({})

    gen.assert_called_once_with("SCEN")
    rep.assert_called_once_with(_AUDIO_RESULT["audio_segments"], _AUDIO_RESULT["beats"], 3)
    upd.assert_called_once_with(7, "audio_prompts_finished")
    assert result["pipeline_step"] == 10
    assert 9 in result["executed_steps"]


@pytest.mark.unit
def test_s9_audio_prompts_no_existing_generates_without_interrupt():
    idea = {"idea_id": 7, "idea_name": "X", "exists": True}
    with (
        patch("app.graph.fetch_idea_by_status", return_value=idea),
        patch("app.graph.fetch_rows", side_effect=_fetch_rows_for_s9_no_existing),
        patch("app.graph.interrupt") as itr,
        patch("app.graph.generate_audio_prompts", return_value=_AUDIO_RESULT) as gen,
        patch("app.graph.replace_audio_prompts") as rep,
        patch("app.graph.update_idea_status") as upd,
    ):
        result = s9_audio_prompts({})

    itr.assert_not_called()
    gen.assert_called_once_with("SCEN")
    rep.assert_called_once_with(_AUDIO_RESULT["audio_segments"], _AUDIO_RESULT["beats"], 3)
    upd.assert_called_once_with(7, "audio_prompts_finished")
    assert result["pipeline_step"] == 10
    assert 9 in result["executed_steps"]


@pytest.mark.unit
def test_s9_audio_prompts_advances_without_work_when_no_idea():
    with (
        patch("app.graph.fetch_idea_by_status", return_value={"exists": False}),
        patch("app.graph.interrupt") as itr,
        patch("app.graph.generate_audio_prompts") as gen,
        patch("app.graph.replace_audio_prompts") as rep,
    ):
        result = s9_audio_prompts({})

    itr.assert_not_called()
    gen.assert_not_called()
    rep.assert_not_called()
    assert result["pipeline_step"] == 10
    assert 9 in result["executed_steps"]


# --- stub factory s10..s13 ---


@pytest.mark.unit
def test_make_stub_prints_and_advances(capsys):
    stub = _make_stub(10)
    with patch("app.graph.fetch_idea_by_status", return_value={"idea_name": "X", "exists": True}):
        result = stub({})

    assert result["pipeline_step"] == 11
    assert 10 in result["executed_steps"]
    assert "STATE 10" in capsys.readouterr().out

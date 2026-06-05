from unittest.mock import patch

import pytest
from langgraph.graph import END

from app.graph import (
    _make_stub,
    _route_dispatch,
    _route_s1,
    _route_s4,
    dispatch,
    s5_scenario,
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
    assert select_target_step({"audio_generated"}, 5) == 10


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


# --- stub factory s6..s12 ---


@pytest.mark.unit
def test_make_stub_prints_and_advances(capsys):
    stub = _make_stub(7)
    with patch("app.graph.fetch_idea_by_status", return_value={"idea_name": "X", "exists": True}):
        result = stub({})

    assert result["pipeline_step"] == 8
    assert 7 in result["executed_steps"]
    assert "STATE 7" in capsys.readouterr().out

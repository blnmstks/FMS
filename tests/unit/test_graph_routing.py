from unittest.mock import patch

import pytest
from langgraph.graph import END

from app.graph import _route_s1, _route_s4, _route_s5, s5_scenario


@pytest.mark.unit
def test_route_s1_goes_to_s2_when_screenshots():
    state = {"use_screenshots": True}
    assert _route_s1(state) == "s2"


@pytest.mark.unit
def test_route_s1_goes_to_s3_when_manual():
    state = {"use_screenshots": False}
    assert _route_s1(state) == "s3"


@pytest.mark.unit
def test_route_s1_goes_to_s3_when_flag_absent():
    assert _route_s1({}) == "s3"


@pytest.mark.unit
def test_route_s4_goes_to_pick_when_ideas_generated():
    state = {"generated_ideas": ["a", "b"]}
    assert _route_s4(state) == "s4_pick"


@pytest.mark.unit
def test_route_s4_goes_to_s5_when_no_generated_ideas():
    assert _route_s4({}) == "s5"


@pytest.mark.unit
def test_route_s4_goes_to_s5_when_raw_idea_exists():
    state = {"raw_idea_exists": True, "idea_name": "existing"}
    assert _route_s4(state) == "s5"


@pytest.mark.unit
def test_route_s5_goes_back_to_s4_when_no_raw_idea():
    assert _route_s5({"raw_idea_exists": False}) == "s4"


@pytest.mark.unit
def test_route_s5_goes_back_to_s4_when_flag_absent():
    assert _route_s5({}) == "s4"


@pytest.mark.unit
def test_route_s5_ends_when_raw_idea_exists():
    assert _route_s5({"raw_idea_exists": True}) == END


@pytest.mark.unit
def test_s5_scenario_no_idea_prints_message_and_flags_missing(capsys):
    with patch("app.graph.fetch_raw_idea", return_value={"raw_idea_exists": False}):
        result = s5_scenario({})
    assert result == {"raw_idea_exists": False}
    assert "there is no idea for scenario" in capsys.readouterr().out


@pytest.mark.unit
def test_s5_scenario_returns_idea_from_db():
    idea = {"idea_id": 7, "idea_name": "X", "raw_idea_exists": True}
    with patch("app.graph.fetch_raw_idea", return_value=idea):
        result = s5_scenario({})
    assert result["idea_id"] == 7
    assert result["idea_name"] == "X"
    assert result["raw_idea_exists"] is True

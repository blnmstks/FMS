import pytest

from app.graph import _route_s1, _route_s4


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

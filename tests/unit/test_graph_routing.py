import pytest
from app.graph import _route_s1


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

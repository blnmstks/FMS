import json

import pytest

from app.utils.workflow import load_workflow, set_node_input


@pytest.mark.unit
def test_load_workflow_parses_json_file(tmp_path):
    wf = {"6": {"class_type": "CLIPTextEncode", "inputs": {"text": "hi"}}}
    path = tmp_path / "wf.json"
    path.write_text(json.dumps(wf), encoding="utf-8")

    assert load_workflow(str(path)) == wf


@pytest.mark.unit
def test_set_node_input_sets_value_and_returns_same_object():
    wf = {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "old", "clip": ["4", 1]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ComfyUI"}},
    }

    result = set_node_input(wf, "6", "text", "new")

    assert result is wf
    assert wf["6"]["inputs"]["text"] == "new"
    # прочие входы целевой ноды не тронуты
    assert wf["6"]["inputs"]["clip"] == ["4", 1]
    # другая нода не тронута
    assert wf["9"]["inputs"]["filename_prefix"] == "ComfyUI"

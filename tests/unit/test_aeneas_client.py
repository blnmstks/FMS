import json
import sys
import types
from unittest.mock import patch

import pytest


def _fake_aeneas_modules(sync_map_json: str, created_tasks: list):
    """Собирает фейковые модули aeneas для подмены ленивого импорта внутри align."""

    class FakeSyncMap:
        def __init__(self, s):
            self.json_string = s

    class FakeTask:
        def __init__(self, config_string=None):
            self.config_string = config_string
            self.audio_file_path_absolute = None
            self.text_file_path_absolute = None
            self.sync_map = None
            created_tasks.append(self)

    class FakeExecuteTask:
        def __init__(self, task):
            self.task = task

        def execute(self):
            self.task.sync_map = FakeSyncMap(sync_map_json)

    task_mod = types.ModuleType("aeneas.task")
    task_mod.Task = FakeTask
    executetask_mod = types.ModuleType("aeneas.executetask")
    executetask_mod.ExecuteTask = FakeExecuteTask
    return {
        "aeneas": types.ModuleType("aeneas"),
        "aeneas.task": task_mod,
        "aeneas.executetask": executetask_mod,
    }


_SYNC_MAP = json.dumps(
    {
        "fragments": [
            {"begin": "0.000", "end": "1.500", "lines": ["A"]},
            {"begin": "1.500", "end": "3.000", "lines": ["B"]},
        ]
    }
)


@pytest.mark.unit
def test_align_parses_spans_in_order():
    from app.infrastructure import aeneas_client

    created = []
    with patch.dict(sys.modules, _fake_aeneas_modules(_SYNC_MAP, created)):
        spans = aeneas_client.align("/tmp/x.wav", ["A", "B"])

    assert spans == [(0.0, 1.5), (1.5, 3.0)]


@pytest.mark.unit
def test_align_skips_empty_line_fragments():
    from app.infrastructure import aeneas_client

    sync_map = json.dumps(
        {
            "fragments": [
                {"begin": "0.000", "end": "0.100", "lines": []},
                {"begin": "0.100", "end": "1.000", "lines": ["A"]},
            ]
        }
    )
    created = []
    with patch.dict(sys.modules, _fake_aeneas_modules(sync_map, created)):
        spans = aeneas_client.align("/tmp/x.wav", ["A"])

    assert spans == [(0.1, 1.0)]


@pytest.mark.unit
def test_align_configures_task_with_config_and_absolute_audio_path():
    from app.infrastructure import aeneas_client

    created = []
    with patch.dict(sys.modules, _fake_aeneas_modules(_SYNC_MAP, created)):
        aeneas_client.align("/tmp/x.wav", ["A", "B"])

    assert len(created) == 1
    task = created[0]
    for key in ("task_language=eng", "is_text_type=plain", "os_task_file_format=json"):
        assert key in task.config_string
    assert task.audio_file_path_absolute.endswith("x.wav")

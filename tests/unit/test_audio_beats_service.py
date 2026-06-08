from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import AUDIO_DIR

# --- snap_boundaries ---


@pytest.mark.unit
def test_snap_boundaries_single_beat_is_whole_file():
    from app.services.audio_beats import snap_boundaries

    assert snap_boundaries([(0.5, 2.0)], 3000) == [(0, 3000)]


@pytest.mark.unit
def test_snap_boundaries_two_beats_stitch_at_pause_midpoint():
    from app.services.audio_beats import PAD_MS, snap_boundaries

    cuts = snap_boundaries([(0.0, 1.0), (1.5, 2.5)], 3000)

    mid = (1000 + 1500) / 2  # 1250
    assert len(cuts) == 2
    assert cuts[0] == (0, mid)
    assert cuts[1] == (mid - PAD_MS, 3000)
    assert cuts[0][0] == 0
    assert cuts[-1][1] == 3000


# --- slice_segment_beats ---


@pytest.mark.unit
def test_slice_segment_beats_builds_manifest():
    from app.services.audio_beats import slice_segment_beats

    voiced = [{"id": 3, "audio_text": "A"}, {"id": 4, "audio_text": "B"}]
    with (
        patch("app.services.audio_beats.align", return_value=[(0.0, 1.0), (1.0, 2.0)]) as al,
        patch("app.services.audio_beats.wav_duration_ms", return_value=2000.0),
        patch(
            "app.services.audio_beats.slice_wav",
            side_effect=lambda src, dst, start, end: dst,
        ) as sl,
    ):
        manifest = slice_segment_beats("seg.wav", voiced, 7, 11)

    al.assert_called_once_with("seg.wav", ["A", "B"])
    assert len(manifest) == 2

    assert manifest[0]["beat_id"] == 3
    assert manifest[1]["beat_id"] == 4
    assert manifest[0]["path"].startswith(str(Path(AUDIO_DIR) / "beats"))
    assert "idea-7-seg-11-beat-3" in manifest[0]["path"]
    assert manifest[0]["path"].endswith(".wav")
    assert manifest[0]["duration"] > 0

    # slice_wav вызван на каждый бит, исходник — путь сегмента, dst == путь из манифеста
    assert sl.call_count == 2
    first_args = sl.call_args_list[0].args
    assert first_args[0] == "seg.wav"
    assert first_args[1] == manifest[0]["path"]

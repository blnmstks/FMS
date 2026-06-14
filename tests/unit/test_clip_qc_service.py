import json
from unittest.mock import MagicMock, patch

import pytest

_VERDICT = {
    "face_visible_in_final_frame": False,
    "same_character_as_reference": True,
    "severe_artifacts": False,
    "verdict": "fail",
    "reason": "face covered by a paper bag",
}


@pytest.mark.unit
def test_qc_frame_paths_returns_first_mid_last_under_qc_dir(tmp_path):
    with patch("app.services.clip_qc.VIDEOS_DIR", str(tmp_path / "vid")):
        from app.services.clip_qc import qc_frame_paths

        paths = qc_frame_paths("clips/idea-1-beat-3-ts.mp4")

    qc_dir = f"{tmp_path / 'vid'}/frames/qc"
    assert paths == [
        f"{qc_dir}/idea-1-beat-3-ts-first.png",
        f"{qc_dir}/idea-1-beat-3-ts-mid.png",
        f"{qc_dir}/idea-1-beat-3-ts-last.png",
    ]


@pytest.fixture
def mock_qc_env(tmp_path, mock_llm_response):
    """Мокает кадры/LLM вокруг review_clip; кадры «извлекаются» возвратом своего пути."""
    with (
        patch("app.services.clip_qc.VIDEOS_DIR", str(tmp_path / "vid")),
        patch("app.services.clip_qc.extract_frame_at", side_effect=lambda _c, _t, out: out) as fat,
        patch("app.services.clip_qc.extract_last_frame", side_effect=lambda _c, out: out) as flast,
        patch("app.services.clip_qc.encode_images", return_value=[{"type": "image_url"}]) as enc,
        patch("app.services.clip_qc.get_client") as client,
    ):
        client.return_value.chat.completions.create.return_value = mock_llm_response(_VERDICT)
        yield {
            "extract_frame_at": fat,
            "extract_last_frame": flast,
            "encode_images": enc,
            "create": client.return_value.chat.completions.create,
            "videos_dir": str(tmp_path / "vid"),
        }


@pytest.mark.unit
def test_review_clip_extracts_first_mid_last_frames(mock_qc_env):
    from app.services.clip_qc import review_clip

    review_clip("clips/idea-1-beat-3-ts.mp4", "ref.png", 4.0)

    qc_dir = f"{mock_qc_env['videos_dir']}/frames/qc"
    fat_calls = mock_qc_env["extract_frame_at"].call_args_list
    assert fat_calls[0].args == (
        "clips/idea-1-beat-3-ts.mp4",
        0.0,
        f"{qc_dir}/idea-1-beat-3-ts-first.png",
    )
    assert fat_calls[1].args == (
        "clips/idea-1-beat-3-ts.mp4",
        2.0,
        f"{qc_dir}/idea-1-beat-3-ts-mid.png",
    )
    mock_qc_env["extract_last_frame"].assert_called_once_with(
        "clips/idea-1-beat-3-ts.mp4", f"{qc_dir}/idea-1-beat-3-ts-last.png"
    )


@pytest.mark.unit
def test_review_clip_sends_reference_first_then_clip_frames(mock_qc_env):
    from app.services.clip_qc import review_clip

    review_clip("clips/c.mp4", "ref.png", 3.0)

    qc_dir = f"{mock_qc_env['videos_dir']}/frames/qc"
    mock_qc_env["encode_images"].assert_called_once_with(
        ["ref.png", f"{qc_dir}/c-first.png", f"{qc_dir}/c-mid.png", f"{qc_dir}/c-last.png"]
    )


@pytest.mark.unit
def test_review_clip_builds_vision_call_with_json_format(mock_qc_env):
    from app.prompts.clip_qc import CLIP_QC_PROMPT
    from app.services.clip_qc import review_clip

    review_clip("clips/c.mp4", "ref.png", 3.0)

    kwargs = mock_qc_env["create"].call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    user_content = kwargs["messages"][1]["content"]
    assert user_content[0] == {"type": "text", "text": CLIP_QC_PROMPT}
    assert user_content[1:] == [{"type": "image_url"}]


@pytest.mark.unit
def test_review_clip_returns_parsed_verdict(mock_qc_env):
    from app.services.clip_qc import review_clip

    result = review_clip("clips/c.mp4", "ref.png", 3.0)

    assert result == _VERDICT
    assert result["verdict"] == "fail"


@pytest.mark.unit
def test_review_clip_raises_on_invalid_json(mock_qc_env):
    from app.services.clip_qc import review_clip

    bad = MagicMock()
    bad.choices[0].message.content = "not a json"
    mock_qc_env["create"].return_value = bad

    with pytest.raises(json.JSONDecodeError):
        review_clip("clips/c.mp4", "ref.png", 3.0)

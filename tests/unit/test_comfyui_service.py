import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_resolve_output_path_keeps_absolute():
    from app.services.comfyui import resolve_output_path

    assert resolve_output_path("/abs/x.png", "wf.json", "assets/images") == "/abs/x.png"


@pytest.mark.unit
def test_resolve_output_path_puts_relative_under_images_dir():
    from app.services.comfyui import resolve_output_path

    result = resolve_output_path("x.png", "wf.json", "assets/images")

    assert result == str(Path("assets/images") / "x.png")


@pytest.mark.unit
def test_resolve_output_path_default_name_from_workflow_stem():
    from app.services.comfyui import resolve_output_path

    result = resolve_output_path(None, "comfyui_workflows/portrait_001.json", "assets/images")

    assert result.startswith(str(Path("assets/images")))
    assert "portrait_001" in result
    assert result.endswith(".png")


@pytest.mark.unit
def test_build_prompt_text_joins_fields_in_order():
    from app.db import IMAGE_PROMPT_FIELDS
    from app.services.comfyui import build_prompt_text

    image_prompt = {f: f"v_{f}" for f in IMAGE_PROMPT_FIELDS}
    image_prompt["id"] = 9  # лишние ключи строки БД игнорируются
    image_prompt["scenario"] = 3

    result = build_prompt_text(image_prompt)

    assert result == ", ".join(f"v_{f}" for f in IMAGE_PROMPT_FIELDS)


@pytest.mark.unit
def test_build_prompt_text_skips_empty_fields():
    from app.services.comfyui import build_prompt_text

    result = build_prompt_text(
        {"image_prompt": "a fox", "camera_angle": "", "lighting": None, "mood": "calm"}
    )

    assert result == "a fox, calm"


@pytest.mark.unit
def test_generate_first_beat_image_delegates_to_generate_image():
    from app.config import COMFYUI_IMAGE_PROMPT_NODE, COMFYUI_IMAGE_WORKFLOW, IMAGES_DIR
    from app.services.comfyui import build_prompt_text, generate_first_beat_image

    image_prompt = {"image_prompt": "a fox", "mood": "calm"}
    with patch("app.services.comfyui.generate_image", return_value="assets/images/x.png") as gen:
        result = generate_first_beat_image(image_prompt, 7)

    assert result == "assets/images/x.png"
    args, kwargs = gen.call_args
    called = list(args) + list(kwargs.values())
    assert COMFYUI_IMAGE_WORKFLOW in called
    assert COMFYUI_IMAGE_PROMPT_NODE in called
    assert build_prompt_text(image_prompt) in called
    output_path = next(a for a in called if str(a).endswith(".png") and "idea-7" in str(a))
    assert output_path.startswith(str(Path(IMAGES_DIR)))


def _write_workflow(tmp_path):
    wf = {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
        "10": {"class_type": "LoadImage", "inputs": {"image": ""}},
    }
    path = tmp_path / "wf.json"
    path.write_text(json.dumps(wf), encoding="utf-8")
    return str(path)


@pytest.fixture
def mock_client():
    """Patch all comfyui_client functions used by the service."""
    with (
        patch("app.services.comfyui.upload_image") as upload,
        patch("app.services.comfyui.queue_prompt") as queue,
        patch("app.services.comfyui.get_history") as history,
        patch("app.services.comfyui.download_image") as download,
    ):
        queue.return_value = "pid-1"
        history.return_value = {
            "pid-1": {
                "outputs": {
                    "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}
                }
            }
        }
        download.return_value = b"IMGDATA"
        upload.return_value = {"name": "uploaded.png", "subfolder": "", "type": "input"}
        yield {
            "upload": upload,
            "queue": queue,
            "history": history,
            "download": download,
        }


@pytest.mark.unit
def test_generate_image_substitutes_prompt(tmp_path, mock_client):
    from app.services.comfyui import generate_image

    wf_path = _write_workflow(tmp_path)
    out = tmp_path / "result.png"

    generate_image(wf_path, "a red fox", "6", str(out))

    sent_wf = mock_client["queue"].call_args.args[0]
    assert sent_wf["6"]["inputs"]["text"] == "a red fox"


@pytest.mark.unit
def test_generate_image_uploads_and_sets_image_when_path_given(tmp_path, mock_client):
    from app.services.comfyui import generate_image

    wf_path = _write_workflow(tmp_path)
    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG")
    out = tmp_path / "result.png"

    generate_image(wf_path, "a red fox", "6", str(out), image_path=str(img), image_node_id="10")

    mock_client["upload"].assert_called_once_with(str(img))
    sent_wf = mock_client["queue"].call_args.args[0]
    assert sent_wf["10"]["inputs"]["image"] == "uploaded.png"


@pytest.mark.unit
def test_generate_image_skips_upload_when_no_image(tmp_path, mock_client):
    from app.services.comfyui import generate_image

    wf_path = _write_workflow(tmp_path)
    out = tmp_path / "result.png"

    generate_image(wf_path, "a red fox", "6", str(out))

    mock_client["upload"].assert_not_called()


@pytest.mark.unit
def test_generate_image_saves_downloaded_bytes_and_returns_path(tmp_path, mock_client):
    from app.services.comfyui import generate_image

    wf_path = _write_workflow(tmp_path)
    out = tmp_path / "nested" / "result.png"

    result = generate_image(wf_path, "a red fox", "6", str(out))

    assert result == str(out)
    assert out.read_bytes() == b"IMGDATA"
    mock_client["download"].assert_called_once_with("out.png", "", "output")


@pytest.mark.unit
def test_generate_image_times_out_when_no_outputs(tmp_path, mock_client):
    from app.services.comfyui import generate_image

    wf_path = _write_workflow(tmp_path)
    out = tmp_path / "result.png"
    mock_client["history"].return_value = {}  # никогда не готово

    with patch("app.services.comfyui.time.sleep"):
        with pytest.raises(TimeoutError):
            generate_image(wf_path, "a red fox", "6", str(out), poll_interval=0, timeout=0.01)

    assert not out.exists()


# --- видео-клип (шаг 13) ---


@pytest.mark.unit
def test_first_output_file_finds_non_image_keys():
    from app.services.comfyui import _first_output_file

    outputs = {"n": {"gifs": [{"filename": "c.mp4", "subfolder": "", "type": "output"}]}}

    assert _first_output_file(outputs) == {"filename": "c.mp4", "subfolder": "", "type": "output"}


@pytest.mark.unit
def test_first_output_file_returns_none_when_no_files():
    from app.services.comfyui import _first_output_file

    assert _first_output_file({"n": {"text": ["x"]}}) is None


@pytest.mark.unit
def test_build_video_prompt_text_joins_fields_in_order():
    from app.db import VIDEO_PROMPT_FIELDS
    from app.services.comfyui import build_video_prompt_text

    row = {f: f"v_{f}" for f in VIDEO_PROMPT_FIELDS}
    row["id"] = 3  # лишние ключи строки БД игнорируются
    row["beat"] = 9

    assert build_video_prompt_text(row) == ", ".join(f"v_{f}" for f in VIDEO_PROMPT_FIELDS)


@pytest.mark.unit
def test_build_video_prompt_text_skips_empty_fields():
    from app.services.comfyui import build_video_prompt_text

    assert build_video_prompt_text({"video_prompt": "pan left", "end_frame": ""}) == "pan left"


def _write_video_workflow(tmp_path):
    from app.config import (
        COMFYUI_VIDEO_AUDIO_NODE,
        COMFYUI_VIDEO_DURATION_NODE,
        COMFYUI_VIDEO_IMAGE_NODE,
        COMFYUI_VIDEO_PROMPT_NODE,
    )

    wf = {
        COMFYUI_VIDEO_PROMPT_NODE: {
            "class_type": "PrimitiveStringMultiline",
            "inputs": {"value": ""},
        },
        COMFYUI_VIDEO_IMAGE_NODE: {"class_type": "LoadImage", "inputs": {"image": ""}},
        COMFYUI_VIDEO_AUDIO_NODE: {"class_type": "LoadAudio", "inputs": {"audio": ""}},
        COMFYUI_VIDEO_DURATION_NODE: {"class_type": "PrimitiveFloat", "inputs": {"value": 0.0}},
        "out": {"class_type": "SaveVideo", "inputs": {}},
    }
    path = tmp_path / "video_wf.json"
    path.write_text(json.dumps(wf), encoding="utf-8")
    return str(path)


@pytest.fixture
def mock_video_client():
    """Patch comfyui_client functions used by generate_beat_clip (вывод видео — под ключом gifs)."""
    with (
        patch("app.services.comfyui.upload_image") as upload_img,
        patch("app.services.comfyui.upload_audio") as upload_aud,
        patch("app.services.comfyui.queue_prompt") as queue,
        patch("app.services.comfyui.get_history") as history,
        patch("app.services.comfyui.download_image") as download,
    ):
        queue.return_value = "vid-1"
        history.return_value = {
            "vid-1": {
                "outputs": {
                    "out": {"gifs": [{"filename": "clip.mp4", "subfolder": "", "type": "output"}]}
                }
            }
        }
        download.return_value = b"VIDDATA"
        upload_img.return_value = {"name": "frame.png", "subfolder": "", "type": "input"}
        upload_aud.return_value = {"name": "beat.wav", "subfolder": "", "type": "input"}
        yield {
            "upload_image": upload_img,
            "upload_audio": upload_aud,
            "queue": queue,
            "history": history,
            "download": download,
        }


@pytest.mark.unit
def test_generate_beat_clip_injects_inputs_and_saves(tmp_path, mock_video_client):
    from app.config import (
        COMFYUI_VIDEO_AUDIO_NODE,
        COMFYUI_VIDEO_DURATION_NODE,
        COMFYUI_VIDEO_IMAGE_NODE,
        COMFYUI_VIDEO_PROMPT_NODE,
    )
    from app.services.comfyui import generate_beat_clip
    from app.utils.audio import write_wav

    wf_path = _write_video_workflow(tmp_path)
    audio = write_wav(b"\x00\x00" * 36000, str(tmp_path / "beat.wav"))  # 1.5 c @ 24000 Hz

    with (
        patch("app.services.comfyui.COMFYUI_VIDEO_WORKFLOW", wf_path),
        patch("app.services.comfyui.VIDEOS_DIR", str(tmp_path / "vid")),
    ):
        result = generate_beat_clip("a clip, wide ending", "frame_in.png", audio, 7, 42)

    mock_video_client["upload_image"].assert_called_once_with("frame_in.png")
    mock_video_client["upload_audio"].assert_called_once_with(audio)
    sent = mock_video_client["queue"].call_args.args[0]
    assert sent[COMFYUI_VIDEO_PROMPT_NODE]["inputs"]["value"] == "a clip, wide ending"
    assert sent[COMFYUI_VIDEO_IMAGE_NODE]["inputs"]["image"] == "frame.png"
    assert sent[COMFYUI_VIDEO_AUDIO_NODE]["inputs"]["audio"] == "beat.wav"
    assert sent[COMFYUI_VIDEO_DURATION_NODE]["inputs"]["value"] == 1.5  # точно, без округления

    assert result.startswith(str(tmp_path / "vid" / "clips"))
    assert "idea-7-beat-42" in result
    assert Path(result).read_bytes() == b"VIDDATA"


@pytest.mark.unit
def test_generate_beat_clip_times_out_when_no_outputs(tmp_path, mock_video_client):
    from app.services.comfyui import generate_beat_clip
    from app.utils.audio import write_wav

    wf_path = _write_video_workflow(tmp_path)
    audio = write_wav(b"\x00\x00" * 2400, str(tmp_path / "beat.wav"))
    mock_video_client["history"].return_value = {}  # никогда не готово

    with (
        patch("app.services.comfyui.COMFYUI_VIDEO_WORKFLOW", wf_path),
        patch("app.services.comfyui.VIDEOS_DIR", str(tmp_path / "vid")),
        patch("app.services.comfyui.time.sleep"),
    ):
        with pytest.raises(TimeoutError):
            generate_beat_clip("p", "f.png", audio, 7, 42, poll_interval=0, timeout=0.01)

    assert not (tmp_path / "vid" / "clips").exists()

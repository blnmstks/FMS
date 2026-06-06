import json
from unittest.mock import patch

import pytest


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

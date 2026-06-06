from unittest.mock import MagicMock, patch

import pytest

from app.config import COMFYUI_URL


@pytest.fixture
def mock_requests():
    with patch("app.infrastructure.comfyui_client.requests") as mock_req:
        yield mock_req


@pytest.mark.unit
def test_upload_image_posts_multipart_and_returns_json(tmp_path, mock_requests):
    from app.infrastructure.comfyui_client import upload_image

    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG\r\n")
    mock_requests.post.return_value.json.return_value = {
        "name": "in.png",
        "subfolder": "",
        "type": "input",
    }

    result = upload_image(str(img))

    args, kwargs = mock_requests.post.call_args
    assert args[0] == f"{COMFYUI_URL}/upload/image"
    assert "image" in kwargs["files"]
    assert result == {"name": "in.png", "subfolder": "", "type": "input"}
    mock_requests.post.return_value.raise_for_status.assert_called_once()


@pytest.mark.unit
def test_queue_prompt_posts_workflow_and_returns_prompt_id(mock_requests):
    from app.infrastructure.comfyui_client import queue_prompt

    wf = {"6": {"inputs": {"text": "hi"}}}
    mock_requests.post.return_value.json.return_value = {"prompt_id": "pid-1"}

    result = queue_prompt(wf, "abc")

    args, kwargs = mock_requests.post.call_args
    assert args[0] == f"{COMFYUI_URL}/prompt"
    assert kwargs["json"] == {"prompt": wf, "client_id": "abc"}
    assert result == "pid-1"
    mock_requests.post.return_value.raise_for_status.assert_called_once()


@pytest.mark.unit
def test_get_history_gets_by_prompt_id_and_returns_json(mock_requests):
    from app.infrastructure.comfyui_client import get_history

    body = {"pid-1": {"outputs": {}, "status": {}}}
    mock_requests.get.return_value.json.return_value = body

    result = get_history("pid-1")

    args, _ = mock_requests.get.call_args
    assert args[0] == f"{COMFYUI_URL}/history/pid-1"
    assert result == body


@pytest.mark.unit
def test_download_image_gets_view_with_params_and_returns_bytes(mock_requests):
    from app.infrastructure.comfyui_client import download_image

    mock_requests.get.return_value.content = b"IMG"

    result = download_image("out.png", "sub", "output")

    args, kwargs = mock_requests.get.call_args
    assert args[0] == f"{COMFYUI_URL}/view"
    assert kwargs["params"] == {
        "filename": "out.png",
        "subfolder": "sub",
        "type": "output",
    }
    assert result == b"IMG"


@pytest.mark.unit
def test_download_image_raises_for_status(mock_requests):
    from app.infrastructure.comfyui_client import download_image

    resp = MagicMock()
    resp.content = b"IMG"
    mock_requests.get.return_value = resp

    download_image("out.png", "", "output")

    resp.raise_for_status.assert_called_once()

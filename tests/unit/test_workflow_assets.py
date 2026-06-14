import pytest

from app.config import (
    COMFYUI_IMAGE_WORKFLOW,
    COMFYUI_VIDEO_AUDIO_NODE,
    COMFYUI_VIDEO_DURATION_NODE,
    COMFYUI_VIDEO_IMAGE_NODE,
    COMFYUI_VIDEO_PROMPT_NODE,
    COMFYUI_VIDEO_WORKFLOW,
)
from app.utils.workflow import load_workflow


@pytest.fixture(scope="module")
def video_wf():
    return load_workflow(COMFYUI_VIDEO_WORKFLOW)


@pytest.fixture(scope="module")
def portrait_wf():
    return load_workflow(COMFYUI_IMAGE_WORKFLOW)


def _nodes_by_class(wf: dict, class_type: str) -> dict:
    return {nid: n for nid, n in wf.items() if n.get("class_type") == class_type}


def _node_by_title(wf: dict, title: str) -> dict:
    found = [n for n in wf.values() if n.get("_meta", {}).get("title") == title]
    assert found, f"нода с титулом {title!r} не найдена"
    return found[0]


@pytest.mark.unit
def test_video_img2video_strength_pinned(video_wf):
    # strength < 1.0 отпускает стартовый кадр: модель уплывает от входа, стыки битов «пыхают»
    nodes = _nodes_by_class(video_wf, "LTXVImgToVideoInplace")
    assert nodes, "в видео-workflow нет нод LTXVImgToVideoInplace"
    for nid, node in nodes.items():
        assert node["inputs"]["strength"] == 1.0, f"нода {nid}: strength != 1.0"


@pytest.mark.unit
def test_video_resolution_is_16x9_and_div64(video_wf):
    # первый проход — половинное разрешение, латенту нужно /32 → полное разрешение /64;
    # 1024×576 — честный 16:9 (720 модель молча резала до 704)
    width = _node_by_title(video_wf, "Width")["inputs"]["value"]
    height = _node_by_title(video_wf, "Height")["inputs"]["value"]
    assert (width, height) == (1024, 576)
    assert width % 64 == 0 and height % 64 == 0


@pytest.mark.unit
def test_video_frame_rate_node_exists_and_is_patchable(video_wf):
    # fps теперь задаётся из конфига (COMFYUI_VIDEO_FPS) и патчится в ноду Frame Rate перед
    # отправкой; значение в JSON — лишь дефолт. Проверяем, что нода на месте и патчабельна.
    from app.config import COMFYUI_VIDEO_FPS_NODE

    assert COMFYUI_VIDEO_FPS_NODE in video_wf
    assert "value" in video_wf[COMFYUI_VIDEO_FPS_NODE]["inputs"]
    assert _node_by_title(video_wf, "Frame Rate") is video_wf[COMFYUI_VIDEO_FPS_NODE]


@pytest.mark.unit
def test_video_config_nodes_exist_with_expected_input_keys(video_wf):
    # пере-экспорт из ComfyUI меняет префиксы subgraph-нод — конфиг должен совпадать с файлом
    expected = {
        COMFYUI_VIDEO_PROMPT_NODE: "value",
        COMFYUI_VIDEO_IMAGE_NODE: "image",
        COMFYUI_VIDEO_AUDIO_NODE: "audio",
        COMFYUI_VIDEO_DURATION_NODE: "value",
    }
    for node_id, key in expected.items():
        assert node_id in video_wf, f"config-нода {node_id} отсутствует в workflow"
        assert key in video_wf[node_id]["inputs"], f"нода {node_id}: нет входа {key!r}"


@pytest.mark.unit
def test_video_has_random_noise_nodes_for_seed_patch(video_wf):
    # generate_beat_clip патчит свежие сиды автопоиском нод RandomNoise
    nodes = _nodes_by_class(video_wf, "RandomNoise")
    assert nodes, "в видео-workflow нет нод RandomNoise"
    for nid, node in nodes.items():
        assert "noise_seed" in node["inputs"], f"нода {nid}: нет входа noise_seed"


@pytest.mark.unit
def test_portrait_resolution_matches_video_aspect(portrait_wf):
    # видео-workflow центр-кропит входную картинку → AR картинки шага 8 обязан совпадать
    latent = _nodes_by_class(portrait_wf, "EmptyFlux2LatentImage")
    scheduler = _nodes_by_class(portrait_wf, "Flux2Scheduler")
    assert latent and scheduler
    for node in list(latent.values()) + list(scheduler.values()):
        assert (node["inputs"]["width"], node["inputs"]["height"]) == (1024, 576)

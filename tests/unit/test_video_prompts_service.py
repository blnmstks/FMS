from unittest.mock import MagicMock, patch

import pytest


def _payload():
    return {
        "beats": [
            {"id": 1, "video_prompt": "vp one", "end_frame": "ef one"},
            {"id": 2, "video_prompt": "vp two", "end_frame": "ef two"},
        ]
    }


# Вход сервиса теперь сегмент-группированный: биты вложены в свой сегмент (один спикер,
# одна просодическая единица), чтобы LLM планировала единую дугу камеры на сегмент.
_SEGMENTS = [
    {
        "seg_id": 1,
        "speaker": "Narrator",
        "emotion": "calm, reflective",
        "tts_text": "Hello there. Goodbye.",
        "duration": 5.3,
        "beats": [
            {"id": 1, "audio_text": "Hello there", "duration": 3.2},
            {"id": 2, "audio_text": "Goodbye", "duration": 2.1},
        ],
    },
]


@pytest.fixture
def _mock_client(mock_llm_response):
    """Patch get_client so no real I/O happens."""
    fake_response = mock_llm_response(_payload())
    with patch("app.services.video_prompts.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = fake_response
        yield mock_get_client


@pytest.mark.unit
def test_generate_video_prompts_returns_beats(_mock_client):
    from app.services.video_prompts import generate_video_prompts

    result = generate_video_prompts("SCEN", {"art_style": "anime"}, [{"label": "Jack"}], _SEGMENTS)

    assert "beats" in result
    assert result["beats"][0]["video_prompt"] == "vp one"
    assert result["beats"][0]["end_frame"] == "ef one"


@pytest.mark.unit
def test_generate_video_prompts_uses_json_response_format(_mock_client):
    from app.services.video_prompts import generate_video_prompts

    generate_video_prompts("SCEN", {"art_style": "anime"}, [{"label": "Jack"}], _SEGMENTS)

    create = _mock_client.return_value.chat.completions.create
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.unit
def test_generate_video_prompts_passes_scenario_style_characters_and_segments(_mock_client):
    from app.services.video_prompts import generate_video_prompts

    generate_video_prompts("SCEN", {"art_style": "anime"}, [{"label": "Jack"}], _SEGMENTS)

    create = _mock_client.return_value.chat.completions.create
    user_content = create.call_args.kwargs["messages"][-1]["content"]
    assert "SCEN" in user_content
    assert "anime" in user_content
    assert "Jack" in user_content
    assert "Narrator" in user_content  # поле сегмента (speaker) — модель видит группировку
    assert "Hello there" in user_content  # audio_text вложенного бита


@pytest.mark.unit
def test_generate_video_prompts_attaches_first_beat_image_and_its_prompt(_mock_client, tmp_path):
    from app.services.video_prompts import generate_video_prompts

    img = tmp_path / "first-beat.png"
    img.write_bytes(b"PNGDATA")
    image_prompt = {"image_prompt": "hero at desk", "camera_angle": "eye-level", "mood": ""}

    generate_video_prompts(
        "SCEN",
        {"art_style": "anime"},
        [{"label": "Jack"}],
        _SEGMENTS,
        first_beat_image_path=str(img),
        image_prompt=image_prompt,
    )

    create = _mock_client.return_value.chat.completions.create
    content = create.call_args.kwargs["messages"][-1]["content"]
    # Мультимодальный content: текст первым, затем картинка (паттерн visual_styles).
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert "SCEN" in content[0]["text"]
    # Текст содержит секцию с image-prompt'ом шага 7 (пустые поля пропущены).
    assert (
        "First-beat image prompt (how the attached beat-1 start frame was generated):"
        in (content[0]["text"])
    )
    assert "image_prompt: hero at desk" in content[0]["text"]
    assert "camera_angle: eye-level" in content[0]["text"]
    assert "mood:" not in content[0]["text"]
    assert content[1]["type"] == "image_url"


@pytest.mark.unit
def test_generate_video_prompts_stays_text_only_without_image(_mock_client):
    from app.services.video_prompts import generate_video_prompts

    generate_video_prompts("SCEN", {"art_style": "anime"}, [{"label": "Jack"}], _SEGMENTS)

    create = _mock_client.return_value.chat.completions.create
    content = create.call_args.kwargs["messages"][-1]["content"]
    # Обратная совместимость: без картинки content — строка, секции image-prompt нет
    # (упоминание «First-beat image prompt» в самом шаблоне v7 — не секция, проверяем заголовок).
    assert isinstance(content, str)
    assert "First-beat image prompt (how the attached beat-1 start frame was generated):" not in (
        content
    )


@pytest.mark.unit
def test_generate_video_prompts_raises_on_bad_json():
    from app.services.video_prompts import generate_video_prompts

    bad_response = MagicMock()
    bad_response.choices[0].message.content = "not json at all"
    bad_response.usage.prompt_tokens = 1
    bad_response.usage.completion_tokens = 1
    bad_response.usage.total_tokens = 2

    import json

    with patch("app.services.video_prompts.get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = bad_response
        with pytest.raises(json.JSONDecodeError):
            generate_video_prompts("SCEN", {}, [], _SEGMENTS)

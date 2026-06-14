"""Regression-guard на ключевые инварианты константы GENERATE_IMAGE_PROMPT_PROMPT (v2).

Семантику промпта юнит-тестом не проверить — это guard от отката к v1-формулировке
(«изобрази открывающие секунды скрипта»), которая давала иллюстративную хук-сцену без
ведущего и морф-артефакт на стыке с битом 1 (см. tests/specs/image_prompts_service.md).
"""

import pytest

from app.prompts.image_prompts import GENERATE_IMAGE_PROMPT_PROMPT


@pytest.mark.unit
def test_image_is_the_first_clip_input_frame():
    # Картинка — буквальный входной кадр первого клипа (I2V анимирует ровно её).
    assert "INPUT FRAME of the first video clip" in GENERATE_IMAGE_PROMPT_PROMPT


@pytest.mark.unit
def test_image_is_identity_reference_for_the_chain():
    # И референс идентичности персонажа на всю цепочку клипов.
    assert "IDENTITY REFERENCE" in GENERATE_IMAGE_PROMPT_PROMPT


@pytest.mark.unit
def test_image_depicts_master_framing_with_character_on_screen():
    # Мастер-кадровка с ведущим в кадре, а не иллюстративная хук-сцена.
    assert "MASTER FRAMING" in GENERATE_IMAGE_PROMPT_PROMPT
    assert "not an illustrative hook scene" in GENERATE_IMAGE_PROMPT_PROMPT
    assert "ON SCREEN" in GENERATE_IMAGE_PROMPT_PROMPT


@pytest.mark.unit
def test_face_readability_and_negative_space_required():
    # Лицо читаемо (якорь идентичности) и есть чистое место под графику.
    assert "fully visible" in GENERATE_IMAGE_PROMPT_PROMPT
    assert "negative space" in GENERATE_IMAGE_PROMPT_PROMPT


@pytest.mark.unit
def test_v3_forbids_readable_text_in_image():
    # v3: на стартовом кадре нет читаемого текста/мелких иконок — видео-модель их не удержит.
    assert "NO readable\n  text" in GENERATE_IMAGE_PROMPT_PROMPT or (
        "NO readable text" in GENERATE_IMAGE_PROMPT_PROMPT.replace("\n  ", " ")
    )
    assert "cannot keep text" in GENERATE_IMAGE_PROMPT_PROMPT
    assert "supporting graphics" not in GENERATE_IMAGE_PROMPT_PROMPT  # призыв убран


@pytest.mark.unit
def test_output_shape_unchanged():
    # Форма ответа не менялась: те же 5 полей (их читает IMAGE_PROMPT_FIELDS-плоскость БД).
    for field in ("image_prompt", "camera_angle", "lighting", "mood", "action"):
        assert f'"{field}"' in GENERATE_IMAGE_PROMPT_PROMPT

"""Regression-guard на ключевые инварианты константы GENERATE_VIDEO_PROMPTS_PROMPT.

Семантику промпта юнит-тестом не проверить — это guard от случайного отката формулировок
доктрины камеры «tripod-first» (v6) и handoff-контракта end_frame (см.
tests/specs/video_prompts_service.md, инвариант 5).
"""

import pytest

from app.prompts.video_prompts import GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_end_frame_is_the_next_clip_handoff_contract():
    # end_frame = первый кадр следующего клипа (единственный носитель идентичности в I2V-цепочке).
    assert "first frame of the next clip" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_end_frame_forbids_character_less_endings():
    # Запрещён безличный/объект-only финал на ЛЮБОМ бите — ровно этот случай ломал стык.
    assert "FORBIDDEN" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "no characters are present" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_end_frame_must_differ_from_video_prompt():
    # end_frame — состояние кадра на стыке, а не копия action из video_prompt.
    assert "MUST DIFFER from video_prompt" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_default_camera_is_static_locked():
    # Ядро v6 (tripod-first): дефолт каждого бита — статичная камера, точной фразой.
    assert "Static camera. Locked frame. No camera movement." in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_camera_move_never_crosses_beat_boundary():
    # Физика сцепки: стык битов — стоп-кадр, скорость камеры не переживает handoff.
    assert "A camera move NEVER crosses a beat boundary" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_camera_move_completes_and_settles():
    # Complete & settle: движение обязано завершиться и осесть в статичный кадр до конца бита.
    assert "settles into a static hold" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_at_most_one_move_beat_per_segment():
    # Ритм: move-бит — редкость; не более одного на сегмент, никогда два подряд.
    assert "at most ONE move-beat per segment" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_one_master_framing_per_segment():
    # Композиция: одна мастер-композиция на сегмент; смена — только на границе сегмента.
    assert "ONE master framing per segment" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_beat_one_is_grounded_on_attached_input_frame():
    # v7: приложенное изображение — буквальный входной кадр бита 1; бит 1 анимирует ровно его.
    assert "FIRST-BEAT INPUT FRAME" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "the literal input frame of beat 1" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "no restaging, no teleports" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_framing_change_must_be_visible_on_screen_motion():
    # v7: смена мастер-композиции — только видимым на экране движением внутри бита 1.
    assert "visible on-screen motion" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_v8_forbids_readable_text_and_small_graphics():
    # v8: LTX-2 не генерирует читаемый текст — корень «чека с каракулями» и каши из иконок.
    assert "GRAPHICS & TEXT" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "cannot render readable or consistent text" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "at MOST ONE large, simple, text-free" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_v8_forbids_dialogue_and_audio_in_prompt():
    # v8: ia2v — звук задан извне, реплики/звук в промпт видеомодели не кладём.
    assert "AUDIO" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "soundtrack is supplied separately" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "lip-synced" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_v8_motion_detailed_natural_sequence_single_action():
    # v8: детальное движение естественной последовательностью + одно действие на бит.
    assert "sequence flowing from beginning to end" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "relationship to the subject" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "ONE clear main action per beat" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_v9_continuity_block_covers_subject_not_just_camera():
    # v9: поза/руки/реквизит/мимика не переживают границу бита (как и скорость камеры).
    assert "CONTINUITY ACROSS THE BEAT BOUNDARY" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_v9_action_begins_from_rest_not_pre_completed():
    # v9: действие пишется как начинающееся из покоя, НЕ как уже завершённое состояние —
    # иначе модель «прыгает» в готовое состояние на frame 0 и стык виден.
    assert "BEGINNING from" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "already-completed" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_v9_forbids_prop_materialization_and_metaphor():
    # v9: реквизит не «появляется» в руке между битами; запрет метафор/намёков на реквизит.
    assert "never simply appears in the hand" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "to suggest holding" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_v9_end_frame_pins_pose_not_just_face():
    # v9: end_frame фиксирует положение рук/реквизита/позы/мимики — handoff-состояние, не только лицо.
    assert "hands and arms" in GENERATE_VIDEO_PROMPTS_PROMPT
    assert "face-only end_frame is insufficient" in GENERATE_VIDEO_PROMPTS_PROMPT


@pytest.mark.unit
def test_starting_frame_lead_sentence_is_an_affirmative_anchor():
    # Текст-якорь стартового кадра для LTX (build_video_prompt_text) — константа в app/prompts/.
    from app.prompts.video_prompts import STARTING_FRAME_LEAD_SENTENCE

    assert "first frame" in STARTING_FRAME_LEAD_SENTENCE
    assert "Do not" not in STARTING_FRAME_LEAD_SENTENCE


@pytest.mark.unit
def test_fixed_video_model_fragments_are_affirmative():
    # Фиксированные фрагменты позитивного промпта видеомодели: hold-фраза утвердительная,
    # запретительного списка («Do not end on…») в них нет — видеомодель не понимает отрицаний.
    from app.prompts.video_prompts import CAMERA_DISCIPLINE_BLOCK, FINAL_FRAME_HOLD_SENTENCE

    assert "fully visible, sharp and clearly readable" in FINAL_FRAME_HOLD_SENTENCE
    assert "Do not end on" not in FINAL_FRAME_HOLD_SENTENCE
    assert CAMERA_DISCIPLINE_BLOCK.startswith("CAMERA DISCIPLINE")
    assert "settles into a static hold" in CAMERA_DISCIPLINE_BLOCK

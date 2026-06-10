import pytest

pytest.importorskip("testcontainers", reason="testcontainers not installed")

import psycopg  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402

CHANNEL_DATA = {
    "channel_name": "IntegrationChannel",
    "channel_description": "Integration test description",
    "channel_avatar": "https://avatar.example.com/img.png",
    "channel_banner": "https://banner.example.com/img.png",
}


@pytest.fixture(scope="module")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        with psycopg.connect(url) as conn:
            conn.execute("""
                CREATE TABLE channel_info (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    avatar TEXT,
                    banner TEXT
                )
            """)
            conn.commit()
        yield url


@pytest.mark.integration
def test_upsert_then_fetch_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.upsert_channel_info(CHANNEL_DATA)
    result = db.fetch_channel_info()

    assert result["channel_name"] == CHANNEL_DATA["channel_name"]
    assert result["channel_description"] == CHANNEL_DATA["channel_description"]
    assert result["channel_avatar"] == CHANNEL_DATA["channel_avatar"]
    assert result["channel_banner"] == CHANNEL_DATA["channel_banner"]
    assert result["channel_info_complete"] is True


@pytest.mark.integration
def test_upsert_twice_updates_not_duplicates(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    updated = {**CHANNEL_DATA, "channel_name": "UpdatedName"}
    db.upsert_channel_info(updated)
    result = db.fetch_channel_info()

    assert result["channel_name"] == "UpdatedName"

    with psycopg.connect(pg_container) as conn:
        count = conn.execute("SELECT COUNT(*) FROM channel_info").fetchone()[0]
    assert count == 1


@pytest.mark.integration
def test_migrate_ideas_table_creates_table(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()

    with psycopg.connect(pg_container) as conn:
        count = conn.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
    assert count == 0


@pytest.mark.integration
def test_insert_idea_then_fetch_raw_idea_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()

    assert db.fetch_raw_idea() == {"raw_idea_exists": False}

    db.insert_idea("My great idea", "raw_idea")
    result = db.fetch_raw_idea()

    assert result["raw_idea_exists"] is True
    assert result["idea_name"] == "My great idea"
    assert isinstance(result["idea_id"], int)


@pytest.mark.integration
def test_migrate_ideas_table_idempotent(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    # Повторный запуск миграции не должен падать (тип и таблица уже существуют).
    db.migrate_ideas_table()
    db.migrate_ideas_table()


@pytest.mark.integration
def test_insert_scenario_links_to_idea_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.migrate_scenarios_table()

    db.insert_idea("Idea for scenario", "raw_idea")
    idea = db.fetch_raw_idea()
    idea_id = idea["idea_id"]

    db.insert_scenario("A dramatic scenario.", idea_id)

    with psycopg.connect(pg_container) as conn:
        row = conn.execute(
            "SELECT scenario, idea FROM scenarios WHERE idea = %s", (idea_id,)
        ).fetchone()
    assert row == ("A dramatic scenario.", idea_id)


@pytest.mark.integration
def test_update_idea_status_advances_and_clears_raw_idea(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()

    db.insert_idea("Idea to advance", "raw_idea")
    with psycopg.connect(pg_container) as conn:
        idea_id = conn.execute(
            "SELECT id FROM ideas WHERE name = %s", ("Idea to advance",)
        ).fetchone()[0]

    db.update_idea_status(idea_id, "scenario_finished")

    with psycopg.connect(pg_container) as conn:
        status = conn.execute("SELECT status FROM ideas WHERE id = %s", (idea_id,)).fetchone()[0]
    assert status == "scenario_finished"


@pytest.mark.integration
def test_insert_image_prompt_links_to_scenario_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.migrate_scenarios_table()
    db.migrate_image_prompts_table()

    db.insert_idea("Idea for image prompt", "clips_visual_style_finished")
    idea_id = db.fetch_idea_by_status("clips_visual_style_finished")["idea_id"]
    db.insert_scenario("A scenario for beats.", idea_id)

    with psycopg.connect(pg_container) as conn:
        scenario_id = conn.execute(
            "SELECT id FROM scenarios WHERE idea = %s", (idea_id,)
        ).fetchone()[0]

    prompt = {f: f"val_{f}" for f in db.IMAGE_PROMPT_FIELDS}
    db.insert_image_prompt(prompt, scenario_id)

    with psycopg.connect(pg_container) as conn:
        row = conn.execute(
            "SELECT image_prompt, action, scenario FROM image_prompts WHERE scenario = %s",
            (scenario_id,),
        ).fetchone()
    assert row == ("val_image_prompt", "val_action", scenario_id)


@pytest.mark.integration
def test_dispatch_helpers_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.insert_idea("Idea A", "scenario_finished")
    db.insert_idea("Idea B", "audio_generated")

    # fetch_present_idea_statuses возвращает уникальные статусы из таблицы.
    assert set(db.fetch_present_idea_statuses()) >= {"scenario_finished", "audio_generated"}

    # fetch_idea_by_status находит идею по конкретному статусу.
    found = db.fetch_idea_by_status("audio_generated")
    assert found["exists"] is True
    assert found["idea_name"] == "Idea B"

    assert db.fetch_idea_by_status("clips_generated") == {"exists": False}


@pytest.mark.integration
def test_insert_image_links_to_image_prompt_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.migrate_scenarios_table()
    db.migrate_image_prompts_table()
    db.migrate_images_table()

    db.insert_idea("Idea for image", "clips_visual_style_finished")
    idea_id = db.fetch_idea_by_status("clips_visual_style_finished")["idea_id"]
    db.insert_scenario("A scenario for beats.", idea_id)

    with psycopg.connect(pg_container) as conn:
        scenario_id = conn.execute(
            "SELECT id FROM scenarios WHERE idea = %s", (idea_id,)
        ).fetchone()[0]

    prompt = {f: f"val_{f}" for f in db.IMAGE_PROMPT_FIELDS}
    db.insert_image_prompt(prompt, scenario_id)

    with psycopg.connect(pg_container) as conn:
        image_prompt_id = conn.execute(
            "SELECT id FROM image_prompts WHERE scenario = %s", (scenario_id,)
        ).fetchone()[0]

    key = f"generated/image_prompt/{image_prompt_id}/01.png"
    db.insert_image("local", key, "generated", image_prompt_id)

    with psycopg.connect(pg_container) as conn:
        row = conn.execute(
            "SELECT storage, key, role, image_prompt FROM images WHERE image_prompt = %s",
            (image_prompt_id,),
        ).fetchone()
    assert row == ("local", key, "generated", image_prompt_id)


@pytest.mark.integration
def test_migrate_audio_seg_prompts_table_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.migrate_scenarios_table()
    db.migrate_audio_seg_prompts_table()

    db.insert_idea("Idea for audio seg", "audio_prompts_finished")
    idea_id = db.fetch_idea_by_status("audio_prompts_finished")["idea_id"]
    db.insert_scenario("A scenario for audio.", idea_id)

    with psycopg.connect(pg_container) as conn:
        scenario_id = conn.execute(
            "SELECT id FROM scenarios WHERE idea = %s", (idea_id,)
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO audio_seg_prompts (speaker, emotion, tts_text, beat_ids, scenario) "
            "VALUES (%s, %s, %s, %s, %s)",
            ("Narrator", "calm", "Hello world.", [1, 2, 3], scenario_id),
        )
        conn.commit()

    with psycopg.connect(pg_container) as conn:
        row = conn.execute(
            "SELECT speaker, emotion, tts_text, beat_ids, scenario "
            "FROM audio_seg_prompts WHERE scenario = %s",
            (scenario_id,),
        ).fetchone()
    assert row == ("Narrator", "calm", "Hello world.", [1, 2, 3], scenario_id)


@pytest.mark.integration
def test_migrate_audio_beat_prompts_table_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.migrate_scenarios_table()
    db.migrate_audio_seg_prompts_table()
    db.migrate_audio_beat_prompts_table()

    db.insert_idea("Idea for audio beat", "audio_prompts_finished")
    idea_id = db.fetch_idea_by_status("audio_prompts_finished")["idea_id"]
    db.insert_scenario("A scenario for audio.", idea_id)

    with psycopg.connect(pg_container) as conn:
        scenario_id = conn.execute(
            "SELECT id FROM scenarios WHERE idea = %s", (idea_id,)
        ).fetchone()[0]

        seg_id = conn.execute(
            "INSERT INTO audio_seg_prompts (speaker, emotion, tts_text, beat_ids, scenario) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING seg_id",
            ("Narrator", "calm", "Hello world.", [1, 2], scenario_id),
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO audio_beat_prompts (seg_id, audio_text) VALUES (%s, %s)",
            (seg_id, "First beat line."),
        )
        conn.commit()

    with psycopg.connect(pg_container) as conn:
        row = conn.execute(
            "SELECT seg_id, audio_text FROM audio_beat_prompts WHERE seg_id = %s",
            (seg_id,),
        ).fetchone()
    assert row == (seg_id, "First beat line.")


@pytest.mark.integration
def test_replace_audio_prompts_round_trip_and_replaces(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.migrate_scenarios_table()
    db.migrate_audio_seg_prompts_table()
    db.migrate_audio_beat_prompts_table()

    db.insert_idea("Idea for replace", "image_generated")
    idea_id = db.fetch_idea_by_status("image_generated")["idea_id"]
    db.insert_scenario("A scenario for replace.", idea_id)
    with psycopg.connect(pg_container) as conn:
        scenario_id = conn.execute(
            "SELECT id FROM scenarios WHERE idea = %s", (idea_id,)
        ).fetchone()[0]

    segments = [
        {"seg_id": 1, "speaker": "Narrator", "emotion": "calm", "tts_text": "Hi.", "beat_ids": [1]},
        {
            "seg_id": 2,
            "speaker": "Host",
            "emotion": "excited",
            "tts_text": "Go!",
            "beat_ids": [2, 3],
        },
    ]
    beats = [
        {"id": 1, "seg_id": 1, "audio_text": "Hi."},
        {"id": 2, "seg_id": 2, "audio_text": "Go!"},
        {"id": 3, "seg_id": None, "audio_text": ""},
    ]
    db.replace_audio_prompts(segments, beats, scenario_id)

    with psycopg.connect(pg_container) as conn:
        seg_rows = conn.execute(
            "SELECT seg_id, speaker, beat_ids FROM audio_seg_prompts WHERE scenario = %s "
            "ORDER BY seg_id",
            (scenario_id,),
        ).fetchall()
        beat_rows = conn.execute(
            "SELECT b.seg_id, b.audio_text FROM audio_beat_prompts b "
            "JOIN audio_seg_prompts s ON s.scenario = %s "
            "WHERE b.seg_id = s.seg_id OR b.seg_id IS NULL "
            "ORDER BY b.id",
            (scenario_id,),
        ).fetchall()

    assert [r[1] for r in seg_rows] == ["Narrator", "Host"]
    assert [r[2] for r in seg_rows] == [[1], [2, 3]]
    db_seg_ids = {r[0] for r in seg_rows}
    # биты ссылаются на реальные seg_id своих сегментов; силентный бит — NULL
    assert beat_rows[0][0] in db_seg_ids
    assert beat_rows[1][0] in db_seg_ids
    assert beat_rows[2] == (None, "")

    # повторный вызов заменяет прежние строки (не накапливает)
    db.replace_audio_prompts(
        [{"seg_id": 1, "speaker": "Solo", "emotion": "flat", "tts_text": "Once.", "beat_ids": [1]}],
        [{"id": 1, "seg_id": 1, "audio_text": "Once."}],
        scenario_id,
    )
    with psycopg.connect(pg_container) as conn:
        seg_count = conn.execute(
            "SELECT count(*) FROM audio_seg_prompts WHERE scenario = %s", (scenario_id,)
        ).fetchone()[0]
        speaker = conn.execute(
            "SELECT speaker FROM audio_seg_prompts WHERE scenario = %s", (scenario_id,)
        ).fetchone()[0]
    assert seg_count == 1
    assert speaker == "Solo"


@pytest.mark.integration
def test_insert_audio_links_to_segment_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.migrate_scenarios_table()
    db.migrate_audio_seg_prompts_table()
    db.migrate_audio_table()

    db.insert_idea("Idea for audio", "audio_prompts_finished")
    idea_id = db.fetch_idea_by_status("audio_prompts_finished")["idea_id"]
    db.insert_scenario("A scenario for audio.", idea_id)

    with psycopg.connect(pg_container) as conn:
        scenario_id = conn.execute(
            "SELECT id FROM scenarios WHERE idea = %s", (idea_id,)
        ).fetchone()[0]
        seg_id = conn.execute(
            "INSERT INTO audio_seg_prompts (speaker, emotion, tts_text, beat_ids, scenario) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING seg_id",
            ("Narrator", "calm", "Hello world.", [1], scenario_id),
        ).fetchone()[0]
        conn.commit()

    key = f"idea-{idea_id}-seg-{seg_id}-ts.wav"
    db.insert_audio("local", key, "segment", seg_id)

    with psycopg.connect(pg_container) as conn:
        row = conn.execute(
            "SELECT storage, key, role, seg_id FROM audio WHERE seg_id = %s",
            (seg_id,),
        ).fetchone()
    assert row == ("local", key, "segment", seg_id)


@pytest.mark.integration
def test_insert_and_delete_audio_beats_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.migrate_scenarios_table()
    db.migrate_audio_seg_prompts_table()
    db.migrate_audio_beat_prompts_table()
    db.migrate_audio_beats_table()

    db.insert_idea("Idea for audio beats", "audio_generated")
    idea_id = db.fetch_idea_by_status("audio_generated")["idea_id"]
    db.insert_scenario("A scenario for audio beats.", idea_id)

    with psycopg.connect(pg_container) as conn:
        scenario_id = conn.execute(
            "SELECT id FROM scenarios WHERE idea = %s", (idea_id,)
        ).fetchone()[0]
        seg_id = conn.execute(
            "INSERT INTO audio_seg_prompts (speaker, emotion, tts_text, beat_ids, scenario) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING seg_id",
            ("Narrator", "calm", "Hello world.", [1], scenario_id),
        ).fetchone()[0]
        beat_id = conn.execute(
            "INSERT INTO audio_beat_prompts (seg_id, audio_text) VALUES (%s, %s) RETURNING id",
            (seg_id, "First beat line."),
        ).fetchone()[0]
        conn.commit()

    key = f"beats/idea-{idea_id}-seg-{seg_id}-beat-{beat_id}-ts.wav"
    db.insert_audio_beat("local", key, "beat", 1.234, beat_id)

    with psycopg.connect(pg_container) as conn:
        row = conn.execute(
            "SELECT storage, key, role, duration, beat FROM audio_beats WHERE beat = %s",
            (beat_id,),
        ).fetchone()
    assert row == ("local", key, "beat", 1.234, beat_id)

    db.delete_audio_beats_for_beats([beat_id])

    with psycopg.connect(pg_container) as conn:
        remaining = conn.execute(
            "SELECT count(*) FROM audio_beats WHERE beat = %s", (beat_id,)
        ).fetchone()[0]
    assert remaining == 0


@pytest.mark.integration
def test_insert_video_clip_links_to_beat_round_trip(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.migrate_scenarios_table()
    db.migrate_audio_seg_prompts_table()
    db.migrate_audio_beat_prompts_table()
    db.migrate_video_clips_table()

    db.insert_idea("Idea for video clips", "video_prompts_finished")
    idea_id = db.fetch_idea_by_status("video_prompts_finished")["idea_id"]
    db.insert_scenario("A scenario for video clips.", idea_id)

    with psycopg.connect(pg_container) as conn:
        scenario_id = conn.execute(
            "SELECT id FROM scenarios WHERE idea = %s", (idea_id,)
        ).fetchone()[0]
        seg_id = conn.execute(
            "INSERT INTO audio_seg_prompts (speaker, emotion, tts_text, beat_ids, scenario) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING seg_id",
            ("Narrator", "calm", "Hello world.", [1], scenario_id),
        ).fetchone()[0]
        beat_id = conn.execute(
            "INSERT INTO audio_beat_prompts (seg_id, audio_text) VALUES (%s, %s) RETURNING id",
            (seg_id, "First beat line."),
        ).fetchone()[0]
        conn.commit()

    key = f"clips/idea-{idea_id}-beat-{beat_id}-ts.mp4"
    db.insert_video_clip("local", key, "clip", beat_id)

    # round-trip через тот же fetch_rows, что использует идемпотентность шага 13
    rows = db.fetch_rows("video_clips", "beat", beat_id)
    assert len(rows) == 1
    assert (rows[0]["storage"], rows[0]["key"], rows[0]["role"], rows[0]["beat"]) == (
        "local",
        key,
        "clip",
        beat_id,
    )


@pytest.mark.integration
def test_replace_video_prompts_round_trip_and_replaces(pg_container, monkeypatch):
    monkeypatch.setenv("DB_URL", pg_container)
    import importlib

    import app.config as cfg

    importlib.reload(cfg)
    import app.db as db

    importlib.reload(db)

    db.migrate_ideas_table()
    db.migrate_scenarios_table()
    db.migrate_audio_seg_prompts_table()
    db.migrate_audio_beat_prompts_table()
    db.migrate_video_beat_prompts_table()

    db.insert_idea("Idea for video prompts", "audio_beats_generated")
    idea_id = db.fetch_idea_by_status("audio_beats_generated")["idea_id"]
    db.insert_scenario("A scenario for video.", idea_id)

    with psycopg.connect(pg_container) as conn:
        scenario_id = conn.execute(
            "SELECT id FROM scenarios WHERE idea = %s", (idea_id,)
        ).fetchone()[0]
        seg_id = conn.execute(
            "INSERT INTO audio_seg_prompts (speaker, emotion, tts_text, beat_ids, scenario) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING seg_id",
            ("Narrator", "calm", "Hello world.", [1, 2], scenario_id),
        ).fetchone()[0]
        beat1 = conn.execute(
            "INSERT INTO audio_beat_prompts (seg_id, audio_text) VALUES (%s, %s) RETURNING id",
            (seg_id, "First beat line."),
        ).fetchone()[0]
        beat2 = conn.execute(
            "INSERT INTO audio_beat_prompts (seg_id, audio_text) VALUES (%s, %s) RETURNING id",
            (seg_id, "Second beat line."),
        ).fetchone()[0]
        conn.commit()

    db.replace_video_prompts(
        [
            {"id": beat1, "video_prompt": "vp one", "end_frame": "ef one"},
            {"id": beat2, "video_prompt": "vp two", "end_frame": "ef two"},
        ],
        scenario_id,
    )

    with psycopg.connect(pg_container) as conn:
        rows = conn.execute(
            "SELECT beat, video_prompt, end_frame FROM video_beat_prompts "
            "WHERE beat IN (%s, %s) ORDER BY beat",
            (beat1, beat2),
        ).fetchall()
    assert rows == [
        (beat1, "vp one", "ef one"),
        (beat2, "vp two", "ef two"),
    ]

    # повторный вызов заменяет прежние строки (не накапливает)
    db.replace_video_prompts(
        [{"id": beat1, "video_prompt": "vp only", "end_frame": "ef only"}],
        scenario_id,
    )
    with psycopg.connect(pg_container) as conn:
        count = conn.execute(
            "SELECT count(*) FROM video_beat_prompts WHERE beat IN (%s, %s)",
            (beat1, beat2),
        ).fetchone()[0]
        vp = conn.execute(
            "SELECT video_prompt FROM video_beat_prompts WHERE beat = %s", (beat1,)
        ).fetchone()[0]
    assert count == 1
    assert vp == "vp only"

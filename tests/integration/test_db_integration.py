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

    assert db.fetch_idea_by_status("video_done") == {"exists": False}


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

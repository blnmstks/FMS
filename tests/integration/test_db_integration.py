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

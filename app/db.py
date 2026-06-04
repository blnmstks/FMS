import psycopg

from app.config import DB_URL


def fetch_channel_info() -> dict:
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, description, avatar, banner FROM channel_info LIMIT 1")
            row = cur.fetchone()
    if row and all(row):
        return {
            "channel_name": row[0],
            "channel_description": row[1],
            "channel_avatar": row[2],
            "channel_banner": row[3],
            "channel_info_complete": True,
        }
    return {"channel_info_complete": False}


def upsert_channel_info(data: dict) -> None:
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM channel_info LIMIT 1")
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE channel_info SET name=%s, description=%s, avatar=%s, banner=%s WHERE id=%s",
                    (data["channel_name"], data["channel_description"],
                     data["channel_avatar"], data["channel_banner"], existing[0]),
                )
            else:
                cur.execute(
                    "INSERT INTO channel_info (name, description, avatar, banner) VALUES (%s,%s,%s,%s)",
                    (data["channel_name"], data["channel_description"],
                     data["channel_avatar"], data["channel_banner"]),
                )
        conn.commit()

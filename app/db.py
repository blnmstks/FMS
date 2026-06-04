import json

import psycopg

from app.config import DB_URL

# Единственный источник истины для названий колонок стилистики.
# Используется в db.py (SQL), graph.py (подсказки пользователю) и services/transcripts.py (парсинг).
IDEAS_STATUSES = [
    "scenario_finished",
    "clips_visual_style_finished",
    "image_prompt_finished",
    "av_prompts_finished",
    "audio_generated",
    "clips_generated",
    "video_done",
]

STYLE_FIELDS = [
    "niche",
    "target_audience",
    "hook_style",
    "script_flow",
    "sentence_rhythm",
    "tone",
    "transitions",
    "curiosity_gaps",
    "emotional_triggers",
    "retention_techniques",
    "direct_address",
    "words_per_second",
    "average_word_count",
    "target_word_count",
]


def migrate_ideas_table() -> None:
    enum_values = ", ".join(f"'{s}'" for s in IDEAS_STATUSES)
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                DO $$ BEGIN
                    CREATE TYPE idea_status AS ENUM ({enum_values});
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END $$
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ideas (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    status idea_status
                )
            """)
        conn.commit()


def fetch_channel_info() -> dict:
    # Читает базовую информацию канала (name, description, avatar, banner).
    # Возвращает полный dict с channel_info_complete=True, или {channel_info_complete: False} если строки нет или есть пустые поля.
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


def migrate_channel_info_style() -> None:
    # Добавляет все колонки стилистики (STYLE_FIELDS) + transcript_files в таблицу channel_info, если их ещё нет.
    # Безопасно запускать многократно — IF NOT EXISTS гарантирует идемпотентность.
    new_cols = STYLE_FIELDS + ["transcript_files"]
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            for col in new_cols:
                cur.execute(f"ALTER TABLE channel_info ADD COLUMN IF NOT EXISTS {col} TEXT")
        conn.commit()


def fetch_channel_style_info() -> dict:
    # Читает все поля анализа стиля контента из БД.
    # Возвращает полный dict с channel_style_complete=True только если все поля непустые,
    # иначе {channel_style_complete: False}. Поле transcript_files возвращается как список (из JSON).
    n = len(STYLE_FIELDS)
    cols = ", ".join(STYLE_FIELDS) + ", transcript_files"
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {cols} FROM channel_info LIMIT 1")
            row = cur.fetchone()
    if row is None:
        return {"channel_style_complete": False}
    style_values = row[:n]
    if not all(v is not None and v != "" for v in style_values):
        return {"channel_style_complete": False}
    result = dict(zip(STYLE_FIELDS, style_values))
    result["transcript_files"] = json.loads(row[n]) if row[n] else []
    result["channel_style_complete"] = True
    return result


def upsert_channel_style_info(style: dict, obsidian_files: list[str]) -> None:
    # Сохраняет результаты стилистического анализа: поля + список имён obsidian-файлов транскриптов.
    # Если строка уже есть — UPDATE, иначе INSERT.
    files_json = json.dumps(obsidian_files)
    cols = STYLE_FIELDS + ["transcript_files"]
    values = [style[f] for f in STYLE_FIELDS] + [files_json]
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM channel_info LIMIT 1")
            existing = cur.fetchone()
            if existing:
                set_clause = ", ".join(f"{c}=%s" for c in cols)
                cur.execute(
                    f"UPDATE channel_info SET {set_clause} WHERE id=%s",
                    values + [existing[0]],
                )
            else:
                col_clause = ", ".join(cols)
                placeholders = ", ".join(["%s"] * len(cols))
                cur.execute(
                    f"INSERT INTO channel_info ({col_clause}) VALUES ({placeholders})",
                    values,
                )
        conn.commit()


def upsert_channel_info(data: dict) -> None:
    # Сохраняет базовую информацию канала (name, description, avatar, banner).
    # Если строка уже есть — UPDATE, иначе INSERT.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM channel_info LIMIT 1")
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE channel_info SET name=%s, description=%s, avatar=%s, banner=%s WHERE id=%s",
                    (
                        data["channel_name"],
                        data["channel_description"],
                        data["channel_avatar"],
                        data["channel_banner"],
                        existing[0],
                    ),
                )
            else:
                cur.execute(
                    "INSERT INTO channel_info (name, description, avatar, banner) VALUES (%s,%s,%s,%s)",
                    (
                        data["channel_name"],
                        data["channel_description"],
                        data["channel_avatar"],
                        data["channel_banner"],
                    ),
                )
        conn.commit()

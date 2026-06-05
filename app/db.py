import json

import psycopg

from app.config import DB_URL

# Единственный источник истины для названий колонок стилистики.
# Используется в db.py (SQL), graph.py (подсказки пользователю) и services/transcripts.py (парсинг).
IDEAS_STATUSES = [
    "raw_idea",
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

# Единственный источник истины для колонок визуального стиля (таблица visual_styles).
VISUAL_STYLE_FIELDS = [
    "art_style",
    "color_pallet",
    "lighting_style",
    "camera_style",
    "composition",
    "detail_level",
    "mood",
]

# Реестр FK-рёбер графа данных: (таблица-потомок, колонка-FK, таблица-родитель),
# смысл — child.<fk_column> -> parent.id. Единственный источник истины для fetch_related.
# ВАЖНО: имена таблиц/колонок берутся ТОЛЬКО отсюда (доверенный whitelist), никогда из
# пользовательского ввода — поэтому их безопасно подставлять в SQL f-строкой.
RELATION_EDGES = [
    ("visual_styles", "channel_info", "channel_info"),
    ("scenarios", "idea", "ideas"),
]


def migrate_ideas_table() -> None:
    # Создаёт ENUM-тип idea_status и таблицу ideas, если их ещё нет, и идемпотентно
    # дополняет уже существующий тип всеми значениями из IDEAS_STATUSES (включая новые).
    # Безопасно запускать многократно.
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
            for status in IDEAS_STATUSES:
                cur.execute(f"ALTER TYPE idea_status ADD VALUE IF NOT EXISTS '{status}'")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ideas (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    status idea_status
                )
            """)
        conn.commit()


def fetch_idea_by_status(status: str) -> dict:
    # Читает первую идею с заданным статусом из таблицы ideas.
    # Возвращает {idea_id, idea_name, exists: True} если найдена, иначе {exists: False}.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM ideas WHERE status = %s LIMIT 1", (status,))
            row = cur.fetchone()
    if row:
        return {"idea_id": row[0], "idea_name": row[1], "exists": True}
    return {"exists": False}


def fetch_raw_idea() -> dict:
    # Тонкая обёртка над fetch_idea_by_status("raw_idea") для шага 5.
    # Возвращает {idea_id, idea_name, raw_idea_exists: True} если найдена, иначе {raw_idea_exists: False}.
    idea = fetch_idea_by_status("raw_idea")
    if idea["exists"]:
        return {
            "idea_id": idea["idea_id"],
            "idea_name": idea["idea_name"],
            "raw_idea_exists": True,
        }
    return {"raw_idea_exists": False}


def fetch_present_idea_statuses() -> list[str]:
    # Возвращает список уникальных статусов идей в таблице (для диспетчера графа).
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT status FROM ideas")
            rows = cur.fetchall()
    return [row[0] for row in rows]


def insert_idea(name: str, status: str) -> None:
    # Вставляет новую идею в таблицу ideas.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ideas (name, status) VALUES (%s, %s)",
                (name, status),
            )
        conn.commit()


def update_idea_status(idea_id: int, status: str) -> None:
    # Обновляет статус идеи (например, raw_idea -> scenario_finished).
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ideas SET status = %s WHERE id = %s",
                (status, idea_id),
            )
        conn.commit()


def migrate_scenarios_table() -> None:
    # Создаёт таблицу scenarios, если её ещё нет. Колонка idea — внешний ключ на ideas(id).
    # Безопасно запускать многократно; миграцию ideas нужно выполнять раньше.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scenarios (
                    id SERIAL PRIMARY KEY,
                    scenario TEXT,
                    idea INTEGER REFERENCES ideas(id)
                )
            """)
        conn.commit()


def insert_scenario(scenario: str, idea_id: int) -> None:
    # Вставляет сгенерированный сценарий, связывая его с идеей.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scenarios (scenario, idea) VALUES (%s, %s)",
                (scenario, idea_id),
            )
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


def migrate_channel_info_table() -> None:
    # Идемпотентно создаёт базовую таблицу channel_info (id, name, description, avatar, banner),
    # чтобы проект разворачивался на чистой базе «из коробки». Запускать первой — до
    # migrate_channel_info_style (ALTER) и migrate_visual_styles_table (FK на channel_info(id)).
    # Стилевые колонки тут НЕ добавляются — за них отвечает migrate_channel_info_style.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS channel_info (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    avatar TEXT,
                    banner TEXT
                )
            """)
        conn.commit()


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


def migrate_visual_styles_table() -> None:
    # Идемпотентно создаёт таблицу visual_styles. Колонки стиля берутся из VISUAL_STYLE_FIELDS,
    # channel_info — внешний ключ на channel_info(id). Запускать после того, как channel_info
    # уже существует. Безопасно запускать многократно (CREATE TABLE IF NOT EXISTS).
    style_cols = ",\n                    ".join(f"{f} TEXT" for f in VISUAL_STYLE_FIELDS)
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS visual_styles (
                    id SERIAL PRIMARY KEY,
                    {style_cols},
                    channel_info INTEGER REFERENCES channel_info(id)
                )
            """)
        conn.commit()


def upsert_visual_styles(style: dict, channel_id: int) -> None:
    # Сохраняет визуальный стиль канала — одна строка на канал. Ключ поиска — колонка
    # channel_info. Если строка для канала есть — UPDATE, иначе INSERT.
    cols = VISUAL_STYLE_FIELDS + ["channel_info"]
    values = [style[f] for f in VISUAL_STYLE_FIELDS] + [channel_id]
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM visual_styles WHERE channel_info=%s LIMIT 1", (channel_id,))
            existing = cur.fetchone()
            if existing:
                set_clause = ", ".join(f"{c}=%s" for c in cols)
                cur.execute(
                    f"UPDATE visual_styles SET {set_clause} WHERE id=%s",
                    values + [existing[0]],
                )
            else:
                col_clause = ", ".join(cols)
                placeholders = ", ".join(["%s"] * len(cols))
                cur.execute(
                    f"INSERT INTO visual_styles ({col_clause}) VALUES ({placeholders})",
                    values,
                )
        conn.commit()


def fetch_rows(table: str, column: str, value) -> list[dict]:
    # Generic-помощник: SELECT * FROM {table} WHERE {column} = %s, строки маппятся в dict
    # по именам колонок из cursor.description. Пустой результат → [].
    # table/column должны приходить только из доверенного whitelist (RELATION_EDGES) —
    # они подставляются f-строкой, value передаётся параметром.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE {column} = %s", (value,))
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    return [dict(zip(cols, row)) for row in rows]


def fetch_row_by_id(table: str, value) -> dict | None:
    # Generic-помощник: SELECT * FROM {table} WHERE id = %s LIMIT 1. Возвращает dict
    # (по cursor.description) или None. table — только из доверенного whitelist.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE id = %s LIMIT 1", (value,))
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(cols, row))


def fetch_related(source_table: str, source_id: int) -> dict:
    # Обобщённый обход связей источника в обе стороны по RELATION_EDGES.
    # Возвращает {"source": dict|None, "parents": {table: dict|None}, "children": {table: [dict]}}:
    #   - "children" — строки, ссылающиеся на источник (источник как родитель);
    #   - "parents"  — строки, на которые ссылается источник (источник как потомок).
    source = fetch_row_by_id(source_table, source_id)
    parents: dict = {}
    children: dict = {}
    for child, col, parent in RELATION_EDGES:
        if parent == source_table:
            children[child] = fetch_rows(child, col, source_id)
        if child == source_table and source is not None and source.get(col) is not None:
            parents[parent] = fetch_row_by_id(parent, source[col])
    return {"source": source, "parents": parents, "children": children}

import json

import psycopg
from psycopg.types.json import Jsonb

from app.config import DB_URL

# Единственный источник истины для названий колонок стилистики.
# Используется в db.py (SQL), graph.py (подсказки пользователю) и services/transcripts.py (парсинг).
IDEAS_STATUSES = [
    "raw_idea",
    "scenario_finished",
    "clips_visual_style_finished",
    "image_prompt_finished",
    "image_generated",
    "audio_prompts_finished",
    "audio_generated",
    "audio_beats_generated",
    "video_prompts_finished",
    "clips_generated",
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

# Единственный источник истины для колонок image-prompt первого бита (таблица image_prompts).
IMAGE_PROMPT_FIELDS = [
    "image_prompt",
    "camera_angle",
    "lighting",
    "mood",
    "action",
]

# Единственный источник истины для колонок видео-промпта бита (таблица video_beat_prompts).
VIDEO_PROMPT_FIELDS = [
    "video_prompt",
    "end_frame",
]

# Реестр FK-рёбер графа данных: (таблица-потомок, колонка-FK, таблица-родитель),
# смысл — child.<fk_column> -> parent.id. Единственный источник истины для fetch_related.
# ВАЖНО: имена таблиц/колонок берутся ТОЛЬКО отсюда (доверенный whitelist), никогда из
# пользовательского ввода — поэтому их безопасно подставлять в SQL f-строкой.
RELATION_EDGES = [
    ("visual_styles", "channel_info", "channel_info"),
    ("visual_styles", "idea", "ideas"),
    ("scenarios", "idea", "ideas"),
    ("characters_sheet", "scenario", "scenarios"),
    ("image_prompts", "scenario", "scenarios"),
    ("images", "image_prompt", "image_prompts"),
    ("audio_seg_prompts", "scenario", "scenarios"),
    ("audio_beats", "beat", "audio_beat_prompts"),
    ("video_beat_prompts", "beat", "audio_beat_prompts"),
    ("video_clips", "beat", "audio_beat_prompts"),
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


def migrate_characters_sheet_table() -> None:
    # Идемпотентно создаёт таблицу characters_sheet (персонажи сценария). face/outfit — JSONB,
    # scenario — внешний ключ на scenarios(id). Запускать после миграции scenarios.
    # Безопасно запускать многократно (CREATE TABLE IF NOT EXISTS).
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS characters_sheet (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    face JSONB,
                    build TEXT,
                    outfit JSONB,
                    baseline_neutral_expression TEXT,
                    scenario INTEGER REFERENCES scenarios(id)
                )
            """)
        conn.commit()


def insert_characters(characters: list[dict], scenario_id: int) -> None:
    # Идемпотентно пересоздаёт набор персонажей сценария: сначала удаляет существующих
    # персонажей этого сценария, затем вставляет переданных. Формат персонажа — из ответа
    # LLM (Character Reference Sheet): label/face/build/outfit/baseline_neutral_expression.
    # face/outfit пишутся как JSONB через Jsonb(...).
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM characters_sheet WHERE scenario=%s", (scenario_id,))
            for char in characters:
                cur.execute(
                    "INSERT INTO characters_sheet "
                    "(name, face, build, outfit, baseline_neutral_expression, scenario) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        char.get("label"),
                        Jsonb(char.get("face")),
                        char.get("build"),
                        Jsonb(char.get("outfit")),
                        char.get("baseline_neutral_expression"),
                        scenario_id,
                    ),
                )
        conn.commit()


def migrate_image_prompts_table() -> None:
    # Идемпотентно создаёт таблицу image_prompts (image-prompt первого бита, привязка к сценарию).
    # Колонки полей берутся из IMAGE_PROMPT_FIELDS; scenario — FK на scenarios(id).
    # Запускать после миграции scenarios. Безопасно запускать многократно.
    field_cols = ",\n                    ".join(f"{f} TEXT" for f in IMAGE_PROMPT_FIELDS)
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS image_prompts (
                    id SERIAL PRIMARY KEY,
                    {field_cols},
                    scenario INTEGER REFERENCES scenarios(id)
                )
            """)
        conn.commit()


def insert_image_prompt(prompt: dict, scenario_id: int) -> None:
    # Вставляет сгенерированный image-prompt первого бита, связывая его со сценарием.
    # Формат prompt — из ответа LLM: ключи IMAGE_PROMPT_FIELDS. Каждый вызов — новая строка.
    cols = IMAGE_PROMPT_FIELDS + ["scenario"]
    values = [prompt.get(f) for f in IMAGE_PROMPT_FIELDS] + [scenario_id]
    col_clause = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO image_prompts ({col_clause}) VALUES ({placeholders})",
                values,
            )
        conn.commit()


def migrate_images_table() -> None:
    # Идемпотентно создаёт таблицу images — реестр сгенерированных картинок. В БД хранится не
    # абсолютный путь, а storage-agnostic ключ (key) + маркер бэкенда (storage), чтобы переезд
    # на S3 не требовал миграции схемы. image_prompt — FK на image_prompts(id); created_at
    # заполняет БД. Запускать после миграции image_prompts. Безопасно запускать многократно.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id SERIAL PRIMARY KEY,
                    storage TEXT NOT NULL DEFAULT 'local',
                    key TEXT NOT NULL,
                    role TEXT,
                    image_prompt INTEGER REFERENCES image_prompts(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        conn.commit()


def insert_image(storage: str, key: str, role: str, image_prompt_id: int) -> None:
    # Регистрирует сгенерированную картинку, связывая её с image-prompt. Каждый вызов — новая
    # строка. Колонка created_at не передаётся — её заполняет БД (DEFAULT now()). Аргументы
    # явные, без дефолтов: знание storage=local/role=generated — бизнес-логика будущего сервиса.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO images (storage, key, role, image_prompt) VALUES (%s, %s, %s, %s)",
                (storage, key, role, image_prompt_id),
            )
        conn.commit()


def migrate_audio_seg_prompts_table() -> None:
    # Идемпотентно создаёт таблицу audio_seg_prompts (аудио-сегменты для TTS, привязка к сценарию).
    # seg_id — SERIAL PK (та же семантика, что id в остальных таблицах). beat_ids — массив INTEGER[].
    # scenario — FK на scenarios(id). Запускать после миграции scenarios. Безопасно запускать многократно.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audio_seg_prompts (
                    seg_id SERIAL PRIMARY KEY,
                    speaker VARCHAR,
                    emotion TEXT,
                    tts_text TEXT,
                    beat_ids INTEGER[],
                    scenario INTEGER REFERENCES scenarios(id)
                )
            """)
        conn.commit()


def migrate_audio_beat_prompts_table() -> None:
    # Идемпотентно создаёт таблицу audio_beat_prompts (биты озвучки сегмента). id — SERIAL PK.
    # seg_id — FK на audio_seg_prompts(seg_id) (PK родителя называется seg_id, не id).
    # Запускать после миграции audio_seg_prompts. Безопасно запускать многократно.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audio_beat_prompts (
                    id SERIAL PRIMARY KEY,
                    seg_id INTEGER REFERENCES audio_seg_prompts(seg_id),
                    audio_text TEXT
                )
            """)
        conn.commit()


def replace_audio_prompts(segments: list[dict], beats: list[dict], scenario_id: int) -> None:
    # Идемпотентно пересоздаёт промпты аудио-сегментов и их битов для сценария: сначала удаляет
    # биты (FK), затем сегменты этого сценария, затем вставляет новые. Локальный seg_id из ответа
    # LLM мапится на БД-serial seg_id через RETURNING, чтобы FK битов был корректным. Силентный
    # бит (seg_id=null) пишется с NULL. Один коммит на всю операцию (атомарность).
    # Формат segments/beats — из ответа LLM (audio_segments / beats).
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM audio_beat_prompts WHERE seg_id IN "
                "(SELECT seg_id FROM audio_seg_prompts WHERE scenario=%s)",
                (scenario_id,),
            )
            cur.execute("DELETE FROM audio_seg_prompts WHERE scenario=%s", (scenario_id,))
            seg_id_map: dict = {}
            for seg in segments:
                cur.execute(
                    "INSERT INTO audio_seg_prompts "
                    "(speaker, emotion, tts_text, beat_ids, scenario) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING seg_id",
                    (
                        seg.get("speaker"),
                        seg.get("emotion"),
                        seg.get("tts_text"),
                        seg.get("beat_ids"),
                        scenario_id,
                    ),
                )
                seg_id_map[seg.get("seg_id")] = cur.fetchone()[0]
            for beat in beats:
                local = beat.get("seg_id")
                cur.execute(
                    "INSERT INTO audio_beat_prompts (seg_id, audio_text) VALUES (%s, %s)",
                    (
                        seg_id_map.get(local) if local is not None else None,
                        beat.get("audio_text", ""),
                    ),
                )
        conn.commit()


def migrate_audio_table() -> None:
    # Идемпотентно создаёт таблицу audio — реестр сгенерированных аудио-сегментов (по образцу
    # images: storage-agnostic ключ key + маркер бэкенда storage, чтобы переезд на S3 не требовал
    # миграции схемы). seg_id — FK на audio_seg_prompts(seg_id); created_at заполняет БД.
    # Запускать после migrate_audio_seg_prompts_table. Безопасно запускать многократно.
    # Таблица намеренно НЕ в RELATION_EDGES: PK родителя называется seg_id (не id), а хелперы
    # fetch_related/fetch_row_by_id завязаны на id — читать через fetch_rows("audio","seg_id",...).
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audio (
                    id SERIAL PRIMARY KEY,
                    storage TEXT NOT NULL DEFAULT 'local',
                    key TEXT NOT NULL,
                    role TEXT,
                    seg_id INTEGER REFERENCES audio_seg_prompts(seg_id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        conn.commit()


def insert_audio(storage: str, key: str, role: str, seg_id: int) -> None:
    # Регистрирует сгенерированный аудио-сегмент, связывая его с audio_seg_prompts. Каждый вызов —
    # новая строка. Колонка created_at не передаётся — её заполняет БД (DEFAULT now()). Аргументы
    # явные, без дефолтов: знание storage=local/role=segment — бизнес-логика узла, а не слоя БД.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audio (storage, key, role, seg_id) VALUES (%s, %s, %s, %s)",
                (storage, key, role, seg_id),
            )
        conn.commit()


def migrate_audio_beats_table() -> None:
    # Идемпотентно создаёт таблицу audio_beats — реестр нарезанных аудиобитов (шаг 11), по образцу
    # audio/images: storage-agnostic ключ key + маркер бэкенда storage. Дополнительно хранит duration
    # (реальная длина бита в секундах — уходит в видео-пайплайн). beat — FK на audio_beat_prompts(id);
    # created_at заполняет БД. Запускать после migrate_audio_beat_prompts_table. Безопасно многократно.
    # В отличие от audio, таблица входит в RELATION_EDGES: родитель audio_beat_prompts имеет PK id.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audio_beats (
                    id SERIAL PRIMARY KEY,
                    storage TEXT NOT NULL DEFAULT 'local',
                    key TEXT NOT NULL,
                    role TEXT,
                    duration DOUBLE PRECISION,
                    beat INTEGER REFERENCES audio_beat_prompts(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        conn.commit()


def insert_audio_beat(storage: str, key: str, role: str, duration: float, beat_id: int) -> None:
    # Регистрирует нарезанный аудиобит, связывая его с audio_beat_prompts. Каждый вызов — новая
    # строка. Колонка created_at не передаётся — её заполняет БД (DEFAULT now()). Аргументы явные,
    # без дефолтов: знание storage=local/role=beat — бизнес-логика узла, а не слоя БД.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audio_beats (storage, key, role, duration, beat) "
                "VALUES (%s, %s, %s, %s, %s)",
                (storage, key, role, duration, beat_id),
            )
        conn.commit()


def delete_audio_beats_for_beats(beat_ids: list[int]) -> None:
    # Удаляет строки audio_beats для переданных битов: DELETE ... WHERE beat = ANY(%s). Нужна для
    # чистого повторного прохода частично нарезанного сегмента (идемпотентность без дублей).
    # Пустой список — корректный no-op (= ANY('{}') не совпадает ни с чем).
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM audio_beats WHERE beat = ANY(%s)", (beat_ids,))
        conn.commit()


def migrate_video_beat_prompts_table() -> None:
    # Идемпотентно создаёт таблицу video_beat_prompts — видео-промпт (video_prompt) и финальный
    # кадр (end_frame) на КАЖДЫЙ бит (шаг 12). По образцу audio_beats ссылается на
    # audio_beat_prompts(id): beat — FK на audio_beat_prompts(id). Запускать после
    # migrate_audio_beat_prompts_table. Безопасно запускать многократно.
    # Таблица входит в RELATION_EDGES: родитель audio_beat_prompts имеет PK id, поэтому
    # fetch_related/fetch_rows работают (как пара audio_beats ↔ audio_beat_prompts).
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS video_beat_prompts (
                    id SERIAL PRIMARY KEY,
                    beat INTEGER REFERENCES audio_beat_prompts(id),
                    video_prompt TEXT,
                    end_frame TEXT
                )
            """)
        conn.commit()


def replace_video_prompts(beats: list[dict], scenario_id: int) -> None:
    # Идемпотентно пересоздаёт видео-промпты битов одного сценария (шаг 12). Сначала удаляет
    # прежние строки video_beat_prompts только для битов этого сценария, затем вставляет новые.
    # Формат beats — из ответа LLM: {id (= существующий audio_beat_prompts.id), video_prompt,
    # end_frame}. Один коммит на всю операцию (атомарность). Пустой список — только удаление.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM video_beat_prompts WHERE beat IN "
                "(SELECT id FROM audio_beat_prompts WHERE seg_id IN "
                "(SELECT seg_id FROM audio_seg_prompts WHERE scenario=%s))",
                (scenario_id,),
            )
            for beat in beats:
                cur.execute(
                    "INSERT INTO video_beat_prompts (beat, video_prompt, end_frame) "
                    "VALUES (%s, %s, %s)",
                    (beat.get("id"), beat.get("video_prompt"), beat.get("end_frame")),
                )
        conn.commit()


def migrate_video_clips_table() -> None:
    # Идемпотентно создаёт таблицу video_clips — реестр сгенерированных видео-клипов (шаг 13), по
    # образцу audio_beats/images: storage-agnostic ключ key + маркер бэкенда storage. beat — FK на
    # audio_beat_prompts(id); created_at заполняет БД. Запускать после migrate_audio_beat_prompts_table.
    # Таблица входит в RELATION_EDGES (родитель audio_beat_prompts имеет PK id). Безопасно многократно.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS video_clips (
                    id SERIAL PRIMARY KEY,
                    storage TEXT NOT NULL DEFAULT 'local',
                    key TEXT NOT NULL,
                    role TEXT,
                    beat INTEGER REFERENCES audio_beat_prompts(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        conn.commit()


def insert_video_clip(storage: str, key: str, role: str, beat_id: int) -> None:
    # Регистрирует сгенерированный видео-клип, связывая его с audio_beat_prompts. Каждый вызов —
    # новая строка. created_at не передаётся — её заполняет БД (DEFAULT now()). Аргументы явные,
    # без дефолтов: знание storage=local/role=clip — бизнес-логика узла, а не слоя БД.
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO video_clips (storage, key, role, beat) VALUES (%s, %s, %s, %s)",
                (storage, key, role, beat_id),
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
    # Идемпотентно создаёт таблицу visual_styles (визуальный стиль клипов, привязка к идее).
    # Колонки стиля берутся из VISUAL_STYLE_FIELDS; channel_info — FK на channel_info(id),
    # idea — FK на ideas(id). Запускать после миграций channel_info и ideas. Для уже
    # существующих таблиц колонка idea добавляется идемпотентно через ALTER ... IF NOT EXISTS.
    style_cols = ",\n                    ".join(f"{f} TEXT" for f in VISUAL_STYLE_FIELDS)
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS visual_styles (
                    id SERIAL PRIMARY KEY,
                    {style_cols},
                    channel_info INTEGER REFERENCES channel_info(id),
                    idea INTEGER REFERENCES ideas(id)
                )
            """)
            cur.execute(
                "ALTER TABLE visual_styles ADD COLUMN IF NOT EXISTS idea "
                "INTEGER REFERENCES ideas(id)"
            )
        conn.commit()


def upsert_visual_styles(style: dict, idea_id: int) -> None:
    # Сохраняет визуальный стиль клипов — одна строка на идею. Ключ поиска — колонка idea.
    # Если строка для идеи есть — UPDATE, иначе INSERT. channel_info не заполняется (NULL).
    cols = VISUAL_STYLE_FIELDS + ["idea"]
    values = [style[f] for f in VISUAL_STYLE_FIELDS] + [idea_id]
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM visual_styles WHERE idea=%s LIMIT 1", (idea_id,))
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

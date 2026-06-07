from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.config import VAULT_PATH
from app.db import (
    IDEAS_STATUSES,
    STYLE_FIELDS,
    VISUAL_STYLE_FIELDS,
    fetch_channel_info,
    fetch_channel_style_info,
    fetch_idea_by_status,
    fetch_present_idea_statuses,
    fetch_raw_idea,
    fetch_rows,
    insert_characters,
    insert_idea,
    insert_image,
    insert_image_prompt,
    insert_scenario,
    update_idea_status,
    upsert_visual_styles,
)
from app.services.branding import analyze_channel
from app.services.comfyui import generate_first_beat_image
from app.services.ideas import generate_video_ideas
from app.services.image_prompts import generate_image_prompt
from app.services.scenarios import generate_scenario
from app.services.transcripts import analyze_transcripts
from app.services.visual_styles import generate_visual_style
from app.state import ProjectState
from app.utils.files import read_from_vault, read_text_file, save_to_vault


def s1_channel(state: ProjectState) -> dict:
    # Шаг 1 графа: проверяет наличие данных канала в БД.
    # Если данные есть — предлагает пропустить шаг. Иначе спрашивает: заполнить вручную или через ИИ-анализ скриншотов.
    if state.get("channel_info_complete"):
        summary = (
            f"Channel info already in DB:\n"
            f"  name:        {state['channel_name']}\n"
            f"  description: {state['channel_description']}\n"
            f"  avatar:      {state['channel_avatar']}\n"
            f"  banner:      {state['channel_banner']}\n"
            "Skip this step? (y/n)"
        )
        skip = interrupt(summary)
        if skip.strip().lower() == "y":
            return {}
    choice = interrupt(
        "STATE 1 — How do you want to fill channel info?\n"
        "  1. Enter manually\n"
        "  2. Analyze screenshots with AI\n"
        "Choose (1/2):"
    )
    if choice.strip() == "2":
        return {"use_screenshots": True}
    name = interrupt("STATE 1 — Enter channel name:")
    description = interrupt("STATE 1 — Enter channel description:")
    avatar = interrupt("STATE 1 — Enter avatar URL:")
    banner = interrupt("STATE 1 — Enter banner URL:")
    return {
        "channel_name": name,
        "channel_description": description,
        "channel_avatar": avatar,
        "channel_banner": banner,
        "channel_info_complete": True,
        "use_screenshots": False,
    }


def s2_branding(_: ProjectState) -> dict:
    # Шаг 2 (опциональный): принимает пути к скриншотам канала и через ИИ заполняет базовую информацию.
    # Запускается только если в s1 пользователь выбрал "Analyze screenshots with AI".
    channel_name = interrupt("STATE 2 — Enter the channel name to analyze:")
    paths_raw = interrupt("STATE 2 — Paste screenshot file paths (comma-separated):")
    paths = [p.strip() for p in paths_raw.split(",") if p.strip()]
    result = analyze_channel(channel_name, paths)
    print(
        f"\nBranding brief generated:\n"
        f"  name:         {result['channel_name']}\n"
        f"  description:  {result['channel_description'][:80]}...\n"
        f"  logo prompt:  {result['channel_avatar'][:60]}...\n"
        f"  banner prompt:{result['channel_banner'][:60]}...\n"
    )
    return result


def _s3_manual_entry() -> dict:
    # Вспомогательная: по очереди запрашивает у пользователя значение каждого поля стилистики channel_info.
    # Возвращает dict {field: value} со всеми полями.
    style = {}
    for field in STYLE_FIELDS:
        value = interrupt(f"STATE 3 — Enter value for '{field}':")
        style[field] = value.strip()
    return style


def _s3_ai_entry() -> tuple[list[str], dict]:
    # Вспомогательная: принимает пути к .txt транскриптам, сохраняет их в Obsidian vault как .md,
    # затем отправляет содержимое в ИИ и возвращает (список obsidian-файлов, dict с полями стилистики).
    paths_raw = interrupt("STATE 3 — Paste paths to .txt transcript files (comma-separated):")
    paths = [p.strip() for p in paths_raw.split(",") if p.strip()]

    texts = []
    obsidian_files = []
    for path in paths:
        content = read_text_file(path)
        stem = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
        filename = save_to_vault(content, stem, VAULT_PATH, "transcripts")
        texts.append(content)
        obsidian_files.append(filename)

    print(f"\nSaved {len(obsidian_files)} transcript(s) to vault/transcripts/")
    style_data = analyze_transcripts(texts)
    return obsidian_files, style_data


def s3_transcripts(_: ProjectState) -> dict:
    # Шаг 3 графа: проверяет заполненность полей стилистики channel_info в БД.
    # Если все поля есть — показывает текущие значения и предлагает: продолжить / обновить вручную / обновить через ИИ.
    # Если хоть одно поле пустое — сообщает об этом и обязывает заполнить (пропустить нельзя).
    style = fetch_channel_style_info()
    missing = [f for f in STYLE_FIELDS if not style.get(f)]

    if not missing:
        summary_lines = ["STATE 3 — Channel style already in DB:\n"]
        for field in STYLE_FIELDS:
            summary_lines.append(f"  {field}: {str(style[field])[:80]}")
        summary_lines.append(
            "\n[1] Continue  [2] Update manually  [3] Update with AI\nChoose (1/2/3):"
        )
        choice = interrupt("\n".join(summary_lines))

        if choice.strip() == "1":
            return {"transcript_obsidian_files": style.get("transcript_files", [])}
        elif choice.strip() == "2":
            style_data = _s3_manual_entry()
            return {
                "channel_style": style_data,
                "channel_style_complete": True,
                "transcript_obsidian_files": [],
            }
        else:
            obsidian_files, style_data = _s3_ai_entry()
            return {
                "channel_style": style_data,
                "channel_style_complete": True,
                "transcript_obsidian_files": obsidian_files,
            }

    missing_str = ", ".join(missing)
    choice = interrupt(
        f"STATE 3 — Missing style fields: {missing_str}\n"
        "[1] Enter manually  [2] Use AI\n"
        "Choose (1/2):"
    )
    if choice.strip() == "1":
        style_data = _s3_manual_entry()
        return {
            "channel_style": style_data,
            "channel_style_complete": True,
            "transcript_obsidian_files": [],
        }
    obsidian_files, style_data = _s3_ai_entry()
    return {
        "channel_style": style_data,
        "channel_style_complete": True,
        "transcript_obsidian_files": obsidian_files,
    }


def s4_ideas(_: ProjectState) -> dict:
    # Шаг 4 графа: работа с таблицей ideas.
    # Если уже есть идея со статусом raw_idea — сразу к шагу 5 (роутер уведёт в s5).
    # Иначе спрашивает: сгенерировать идеи через ИИ или ввести свою.
    # Ветка "сгенерировать" завершает узел вызовом LLM (без последующего interrupt),
    # поэтому при resume LLM не вызывается повторно — выбор номера живёт в отдельном узле s4_pick.
    existing = fetch_raw_idea()
    if existing.get("raw_idea_exists"):
        return {
            "idea_name": existing["idea_name"],
            "idea_id": existing["idea_id"],
            "raw_idea_exists": True,
        }

    choice = interrupt(
        "STATE 4 — Do you want me to generate video ideas or do you have your own one?\n"
        "  1. Generate video ideas\n"
        "  2. I have my own idea\n"
        "Choose (1/2):"
    )
    if choice.strip() == "2":
        idea = interrupt("STATE 4 — Enter your video idea:")
        name = idea.strip()
        insert_idea(name, "raw_idea")
        return {"idea_name": name}

    info = fetch_channel_info()
    style = fetch_channel_style_info()
    texts = [
        read_from_vault(f, VAULT_PATH, "transcripts") for f in style.get("transcript_files", [])
    ]
    ideas = generate_video_ideas(
        info.get("channel_name", ""),
        info.get("channel_description", ""),
        style,
        texts,
    )
    return {"generated_ideas": ideas}


def s4_pick(state: ProjectState) -> dict:
    # Показывает сгенерированные идеи и записывает выбранную в ideas со статусом raw_idea.
    ideas = state["generated_ideas"]
    lines = ["Video ideas — in the channel's style:\n"]
    for i, idea in enumerate(ideas, 1):
        lines.append(f"{i}. {idea}")
    lines.append("\nPick a number.")
    pick = interrupt("\n".join(lines))

    raw = pick.strip()
    index = int(raw) - 1 if raw.isdigit() else 0
    index = max(0, min(index, len(ideas) - 1))
    chosen = ideas[index]
    insert_idea(chosen, "raw_idea")
    return {"idea_name": chosen}


# --- Диспетчер шагов 5+: соответствие статус→шаг и выбор целевого шага ---

# Источник истины для соответствия — порядок IDEAS_STATUSES: raw_idea→5 … video_done→13.
STEP_BY_STATUS = {status: 5 + i for i, status in enumerate(IDEAS_STATUSES)}
FIRST_STEP = 5


def select_target_step(present_statuses: set[str], current_step: int) -> int:
    # Чистый выбор шага: свой статус → этот шаг; иначе самый ранний предыдущий;
    # иначе ближайший следующий; совсем нет идей → шаг 4 (создать raw_idea).
    steps = {STEP_BY_STATUS[s] for s in present_statuses if s in STEP_BY_STATUS}
    if not steps:
        return 4
    if current_step in steps:
        return current_step
    earlier = [s for s in steps if s < current_step]
    if earlier:
        return min(earlier)
    return min(s for s in steps if s > current_step)


def _advance(state: ProjectState, step: int, updates: dict | None = None) -> dict:
    # Помечает шаг выполненным за прогон и двигает курсор на следующий.
    executed = list(state.get("executed_steps") or []) + [step]
    return {"pipeline_step": step + 1, "executed_steps": executed, **(updates or {})}


def dispatch(state: ProjectState) -> dict:
    # Узел-диспетчер: по статусам идей в БД вычисляет, какой шаг выполнять.
    present = set(fetch_present_idea_statuses())
    current = state.get("pipeline_step", FIRST_STEP)
    return {"pipeline_target": select_target_step(present, current)}


def s5_scenario(state: ProjectState) -> dict:
    # Шаг 5: по идее со статусом raw_idea генерирует подробный сценарий в стиле канала.
    # Диспетчер заводит сюда только при наличии raw_idea; защитная ветка — на случай гонки.
    idea = fetch_raw_idea()
    if not idea.get("raw_idea_exists"):
        return _advance(state, 5)

    idea_id = idea["idea_id"]
    idea_name = idea["idea_name"]
    print(f"\nSTATE 5 — writing scenario for raw idea: {idea_name}")

    info = fetch_channel_info()
    style = fetch_channel_style_info()
    texts = [
        read_from_vault(f, VAULT_PATH, "transcripts") for f in style.get("transcript_files", [])
    ]
    scenario = generate_scenario(
        idea_name,
        info.get("channel_name", ""),
        info.get("channel_description", ""),
        style,
        texts,
    )
    insert_scenario(scenario, idea_id)
    update_idea_status(idea_id, "scenario_finished")
    print(f"STATE 5 — scenario saved and idea marked scenario_finished: {idea_name}")
    return _advance(state, 5, {"idea_id": idea_id, "idea_name": idea_name, "raw_idea_exists": True})


def s6_visual_style(state: ProjectState) -> dict:
    # Шаг 6: по idea со статусом scenario_finished генерирует визуальный стиль клипов через ИИ
    # на основе приложенных изображений + сценария + Style DNA канала и сохраняет 7 полей стиля
    # в visual_styles (per-idea upsert), переводит идею в clips_visual_style_finished.
    # Узел самодостаточен (не доверяет state — диспетчер может завести сюда в свежем прогоне).
    idea = fetch_idea_by_status("scenario_finished")
    if not idea.get("exists"):
        return _advance(state, 6)

    idea_id = idea["idea_id"]
    idea_name = idea["idea_name"]
    print(f"\nSTATE 6 — extracting visual style for idea: {idea_name}")

    scenarios = fetch_rows("scenarios", "idea", idea_id)
    scenario_row = scenarios[0] if scenarios else {}
    scenario_text = scenario_row.get("scenario", "")
    scenario_id = scenario_row.get("id")

    paths_raw = interrupt("STATE 6 — Paste paths to reference images (comma-separated, ~5):")
    paths = [p.strip() for p in paths_raw.split(",") if p.strip()]

    style = fetch_channel_style_info()
    profile = generate_visual_style(idea_name, scenario_text, style, paths)

    visual = {f: profile[f] for f in VISUAL_STYLE_FIELDS}
    upsert_visual_styles(visual, idea_id)

    characters = profile.get("characters") or []
    if scenario_id is not None:
        insert_characters(characters, scenario_id)
    print(f"STATE 6 — saved {len(characters)} character(s) for scenario {scenario_id}")

    update_idea_status(idea_id, "clips_visual_style_finished")
    print(f"STATE 6 — visual style saved and idea marked clips_visual_style_finished: {idea_name}")
    return _advance(state, 6, {"idea_id": idea_id, "idea_name": idea_name})


def s7_image_prompt(state: ProjectState) -> dict:
    # Шаг 7: по идее со статусом clips_visual_style_finished генерирует через ИИ image-prompt
    # ПЕРВОГО бита сценария и сохраняет его в image_prompts (привязка к сценарию), переводит
    # идею в image_prompt_finished. Узел самодостаточен (не доверяет state).
    # Статус меняется ТОЛЬКО после успешной записи в БД: при ошибке insert_image_prompt
    # исключение пробрасывается, флоу останавливается, статус и курсор не двигаются.
    idea = fetch_idea_by_status("clips_visual_style_finished")
    if not idea.get("exists"):
        return _advance(state, 7)

    idea_id = idea["idea_id"]
    idea_name = idea["idea_name"]

    answer = interrupt("STATE 7 — Already have first beat img? (y/n)")
    if answer.strip().lower() in ("y", "yes"):
        # Картинка первого бита уже есть — пропускаем шаг 8 (генерацию), уводим на шаг 9:
        # выставляем статус, который потребляет шаг 9 (диспетчер сам направит на s9).
        update_idea_status(idea_id, "image_generated")
        return _advance(state, 7, {"idea_id": idea_id, "idea_name": idea_name})

    print(f"\nSTATE 7 — generating first-beat image prompt for idea: {idea_name}")

    scenario_row = (fetch_rows("scenarios", "idea", idea_id) or [{}])[0]
    scenario_text = scenario_row.get("scenario", "")
    scenario_id = scenario_row.get("id")

    visual_row = (fetch_rows("visual_styles", "idea", idea_id) or [{}])[0]
    visual_style = {f: visual_row.get(f) for f in VISUAL_STYLE_FIELDS}

    characters = fetch_rows("characters_sheet", "scenario", scenario_id) if scenario_id else []

    prompt = generate_image_prompt(scenario_text, visual_style, characters)

    if scenario_id is not None:
        insert_image_prompt(prompt, scenario_id)
        update_idea_status(idea_id, "image_prompt_finished")
        print(f"STATE 7 — image prompt saved and idea marked image_prompt_finished: {idea_name}")
    return _advance(state, 7, {"idea_id": idea_id, "idea_name": idea_name})


def s8_generate_image(state: ProjectState) -> dict:
    # Шаг 8: по idea со статусом image_prompt_finished генерирует реальное изображение первого
    # бита через ComfyUI по сохранённому image-prompt, регистрирует его в таблице images и
    # переводит идею в image_generated. Узел самодостаточен, полностью автоматический (без
    # interrupt). Статус меняется ТОЛЬКО после успешной генерации и записи: при ошибке
    # generate_first_beat_image/insert_image исключение пробрасывается, статус и курсор не двигаются.
    idea = fetch_idea_by_status("image_prompt_finished")
    if not idea.get("exists"):
        return _advance(state, 8)

    idea_id = idea["idea_id"]
    idea_name = idea["idea_name"]

    scenario_row = (fetch_rows("scenarios", "idea", idea_id) or [{}])[0]
    scenario_id = scenario_row.get("id")
    image_prompt_row = (
        (fetch_rows("image_prompts", "scenario", scenario_id) or [{}])[0] if scenario_id else {}
    )
    image_prompt_id = image_prompt_row.get("id")
    if image_prompt_id is None:
        return _advance(state, 8, {"idea_id": idea_id, "idea_name": idea_name})

    print(f"\nSTATE 8 — generating first-beat image for idea: {idea_name}")
    path = generate_first_beat_image(image_prompt_row, idea_id)
    insert_image("local", path, "first_beat", image_prompt_id)
    update_idea_status(idea_id, "image_generated")
    print(f"STATE 8 — image saved and idea marked image_generated: {idea_name}")
    return _advance(state, 8, {"idea_id": idea_id, "idea_name": idea_name})


def _make_stub(n: int):
    # Фабрика узлов-заглушек для шагов 9..13: печатает плейсхолдер и продвигает курсор.
    status = IDEAS_STATUSES[n - 5]

    def stub(state: ProjectState) -> dict:
        idea = fetch_idea_by_status(status)
        print(f"\nSTATE {n} — (заглушка) next stage for idea: {idea.get('idea_name')}")
        return _advance(state, n)

    return stub


def _route_s1(state: ProjectState) -> str:
    # Маршрутизатор после шага 1: направляет в s2 если выбраны скриншоты, иначе сразу в s3.
    return "s2" if state.get("use_screenshots") else "s3"


def _route_s4(state: ProjectState) -> str:
    # После шага 4: сгенерированы идеи — к выбору номера (s4_pick), иначе — к диспетчеру.
    return "s4_pick" if state.get("generated_ideas") else "dispatch"


def _route_dispatch(state: ProjectState) -> str:
    # После диспетчера: target=4 — создать идею (s4); если целевой шаг уже выполнялся за этот
    # прогон — завершить (стаб не двигает статус, иначе бесконечный цикл); иначе — на шаг.
    target = state["pipeline_target"]
    if target == 4:
        return "s4"
    if target in (state.get("executed_steps") or []):
        return END
    return f"s{target}"


g = StateGraph(ProjectState)

g.add_node("s1", s1_channel)
g.add_node("s2", s2_branding)
g.add_node("s3", s3_transcripts)
g.add_node("s4", s4_ideas)
g.add_node("s4_pick", s4_pick)
g.add_node("dispatch", dispatch)
g.add_node("s5", s5_scenario)
g.add_node("s6", s6_visual_style)
g.add_node("s7", s7_image_prompt)
g.add_node("s8", s8_generate_image)
for _n in range(9, 14):  # шаги 9..13 — заглушки из фабрики
    g.add_node(f"s{_n}", _make_stub(_n))

g.add_edge(START, "s1")
g.add_conditional_edges("s1", _route_s1, {"s2": "s2", "s3": "s3"})
g.add_edge("s2", "s3")
g.add_edge("s3", "dispatch")
g.add_conditional_edges("s4", _route_s4, {"s4_pick": "s4_pick", "dispatch": "dispatch"})
g.add_edge("s4_pick", "dispatch")

# Диспетчер ведёт на любой из шагов 4..13 или завершает граф.
_dispatch_targets = {f"s{n}": f"s{n}" for n in range(4, 14)}
_dispatch_targets[END] = END
g.add_conditional_edges("dispatch", _route_dispatch, _dispatch_targets)

for _n in range(5, 14):  # после каждого шага конвейера — назад в диспетчер
    g.add_edge(f"s{_n}", "dispatch")


def build_app(checkpointer):
    # Компилирует LangGraph-граф с PostgreSQL-чекпоинтером для сохранения состояния между запусками.
    return g.compile(checkpointer=checkpointer)

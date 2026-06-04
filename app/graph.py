from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.config import VAULT_PATH
from app.db import STYLE_FIELDS, fetch_channel_style_info
from app.services.branding import analyze_channel
from app.services.transcripts import analyze_transcripts
from app.state import ProjectState
from app.utils.files import read_text_file, save_to_vault


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


def _route_s1(state: ProjectState) -> str:
    # Маршрутизатор после шага 1: направляет в s2 если выбраны скриншоты, иначе сразу в s3.
    return "s2" if state.get("use_screenshots") else "s3"


g = StateGraph(ProjectState)

g.add_node("s1", s1_channel)
g.add_node("s2", s2_branding)
g.add_node("s3", s3_transcripts)

g.add_edge(START, "s1")
g.add_conditional_edges("s1", _route_s1, {"s2": "s2", "s3": "s3"})
g.add_edge("s2", "s3")
g.add_edge("s3", END)


def build_app(checkpointer):
    # Компилирует LangGraph-граф с PostgreSQL-чекпоинтером для сохранения состояния между запусками.
    return g.compile(checkpointer=checkpointer)

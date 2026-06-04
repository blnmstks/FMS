from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.services.branding import analyze_channel
from app.state import ProjectState


def s1_channel(state: ProjectState) -> dict:
    """
    Информация о канале берется либо из БД либо корректируется вручную или с помощью ИИ
    """
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


def s3_transcripts(_: ProjectState) -> dict:
    answer = interrupt("STATE 3 — Provide 2–3 FULL video transcripts.")
    return {"transcripts": [answer]}


def _route_s1(state: ProjectState) -> str:
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
    return g.compile(checkpointer=checkpointer)

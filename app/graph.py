from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from app.state import ProjectState


def s1_channel(state: ProjectState) -> dict:
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
    name        = interrupt("STATE 1 — Enter channel name:")
    description = interrupt("STATE 1 — Enter channel description:")
    avatar      = interrupt("STATE 1 — Enter avatar URL:")
    banner      = interrupt("STATE 1 — Enter banner URL:")
    return {
        "channel_name": name,
        "channel_description": description,
        "channel_avatar": avatar,
        "channel_banner": banner,
        "channel_info_complete": True,
    }


def s3_transcripts(_: ProjectState) -> dict:
    answer = interrupt("STATE 3 — Provide 2–3 FULL video transcripts.")
    return {"transcripts": [answer]}


g = StateGraph(ProjectState)

g.add_node("s1", s1_channel)
g.add_node("s3", s3_transcripts)

# ребра
g.add_edge(START, "s1")
g.add_edge("s1", "s3")
g.add_edge("s3", END)


def build_app(checkpointer):
    return g.compile(checkpointer=checkpointer)

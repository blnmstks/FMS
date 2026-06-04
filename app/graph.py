from langgraph.graph import StateGraph, START, END

# checkpointer в оперативной памяти. На фазе 1 он держит состояние между остановкой и резюмом
#  в рамках одного запуска процесса. В фазе 2 заменим его на Postgres, чтобы переживало рестарт
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from app.state import ProjectState

# узел - функция, принимающая текущее состояние и возвращающая словарь с обновлениями
def s1_channel(state: ProjectState) -> dict:
    # останавливает граф и отдаёт вопрос наружу
    answer = interrupt("STATE 1 — What channel do you want to clone?")
    return {"channel": answer}

def s3_transcripts(state: ProjectState) -> dict:
    answer = interrupt("STATE 3 — Provide 2–3 FULL video transcripts.")
    return {"transcripts": [answer]}


g = StateGraph(ProjectState)

g.add_node("s1", s1_channel)
g.add_node("s3", s3_transcripts)

# ребра
g.add_edge(START, "s1")
g.add_edge("s1", "s3")
g.add_edge("s3", END)

app = g.compile(checkpointer=MemorySaver())

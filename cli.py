from langgraph.types import Command
from langgraph.checkpoint.postgres import PostgresSaver

from app.graph import build_app
from app.config import DB_URL, THREAD_ID
from app.db import fetch_channel_info, upsert_channel_info

config = {"configurable": {"thread_id": THREAD_ID}}

with PostgresSaver.from_conn_string(DB_URL) as checkpointer:
    checkpointer.setup()
    app = build_app(checkpointer)

    initial_state = fetch_channel_info()

    state = app.get_state(config)
    if state and state.next:
        interrupted = state.tasks[0].interrupts if state.tasks else []
        result = {"__interrupt__": interrupted} if interrupted else app.invoke(Command(resume=None), config)
    else:
        result = app.invoke(initial_state, config)

    while "__interrupt__" in result:
        question = result["__interrupt__"][0].value
        user_text = input(f"\n{question}\n> ")
        result = app.invoke(Command(resume=user_text), config)

    final = app.get_state(config).values
    if final.get("channel_info_complete"):
        upsert_channel_info(final)

    checkpointer.delete_thread(THREAD_ID)

    print("\n--- готово, финальное состояние: ---")
    print(result)

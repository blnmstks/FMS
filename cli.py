from langgraph.types import Command
from app.graph import build_app, DB_URL

from langgraph.checkpoint.postgres import PostgresSaver

config = {"configurable": {"thread_id": "proj-1"}}

with PostgresSaver.from_conn_string(DB_URL) as checkpointer:
    checkpointer.setup()
    app = build_app(checkpointer)

    # Проверяем, есть ли уже сохранённый checkpoint с активным interrupt
    state = app.get_state(config)
    if state and state.next:
        # Продолжаем с того места, где остановились — не делаем новый invoke({})
        interrupted = state.tasks[0].interrupts if state.tasks else []
        if interrupted:
            result = {"__interrupt__": interrupted}
        else:
            result = app.invoke(Command(resume=None), config)
    else:
        # Свежий запуск: граф идёт от START
        result = app.invoke({}, config)

    while "__interrupt__" in result:
        question = result["__interrupt__"][0].value
        user_text = input(f"\n{question}\n> ")
        result = app.invoke(Command(resume=user_text), config)

    checkpointer.delete_thread(config["configurable"]["thread_id"])

    print("\n--- готово, финальное состояние: ---")
    print(result)
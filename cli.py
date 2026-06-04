from langgraph.types import Command
from app.graph import app

# thread_id - это идентификатор «сессии»: он связывает все вызовы invoke в один непрерывный проход.
config = {"configurable": {"thread_id": "proj-1"}}

# первый вызов: граф идёт от START и встаёт на первом interrupt
result = app.invoke({}, config)

while "__interrupt__" in result:
    question = result["__interrupt__"][0].value
    user_text = input(f"\n{question}\n> ")
    # запускает граф с пустым состоянием. В result будет ключ __interrupt__ с вопросом
    result = app.invoke(Command(resume=user_text), config)

print("\n--- готово, финальное состояние: ---")
print(result)
import json

from app.utils.files import read_text_file


def load_workflow(path: str) -> dict:
    # Читает локальный workflow-файл в API-format и парсит его как JSON.
    return json.loads(read_text_file(path))


def set_node_input(workflow: dict, node_id: str, key: str, value) -> dict:
    # Записывает значение во вход ноды по её id: workflow[node_id]["inputs"][key] = value.
    # Какой именно key (text/image/...) — решает вызывающий код. Возвращает тот же workflow.
    workflow[node_id]["inputs"][key] = value
    return workflow

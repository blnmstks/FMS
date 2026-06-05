# Spec: `app/infrastructure/llm_client`

## `get_client() -> OpenAI`
Создаёт OpenAI-клиент, направленный на OpenRouter (`base_url`, `api_key` из конфига).

## `log_llm_input(messages: list) -> None`

### Contract
Выводит в stdout итоговый инпут (`messages`), который передаётся модели на вход — **ровно
как есть**, без усечения. Сериализует `json.dumps(messages, ensure_ascii=False, indent=2)`
(кириллица и текст печатаются как есть, не эскейпятся в `\uXXXX`), обрамляя заголовком.
Вызывается каждым сервисом перед `chat.completions.create(...)`.

### Invariants
1. Печатает содержимое всех сообщений (роли и контент).
2. `ensure_ascii=False` — не эскейпит не-ASCII символы.
3. Ничего не возвращает; не меняет `messages`.

### Test cases
- **печатает сообщения**: для `[{role: system, content: "be brief"}, {role: user,
  content: "Привет"}]` stdout содержит `system`, `be brief`, `user`, `Привет`

import pytest

from app.infrastructure.llm_client import log_llm_input


@pytest.mark.unit
def test_log_llm_input_prints_roles_and_content(capsys):
    messages = [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "Привет мир"},
    ]

    log_llm_input(messages)

    out = capsys.readouterr().out
    assert "system" in out
    assert "be brief" in out
    assert "user" in out
    assert "Привет мир" in out  # ensure_ascii=False — кириллица как есть


@pytest.mark.unit
def test_log_llm_input_returns_none_and_keeps_messages():
    messages = [{"role": "user", "content": "hi"}]
    assert log_llm_input(messages) is None
    assert messages == [{"role": "user", "content": "hi"}]

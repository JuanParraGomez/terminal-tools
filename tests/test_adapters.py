from __future__ import annotations

import os

from app.adapters.base import AdapterRequest
from app.adapters.cli_ai_adapter import CliAIAgentAdapter
from app.adapters.copilot_adapter import CopilotAdapter


class _FakeExecutor:
    def __init__(self) -> None:
        self.last_command = None
        self.last_cwd = None
        self.last_env = None

    def run(self, command, cwd=None, timeout_seconds=None, env=None):
        self.last_command = command
        self.last_cwd = cwd
        self.last_env = env
        return {"ok": True, "stdout": "ok", "stderr": "", "returncode": 0}


class _FakeCopilotSettings:
    default_timeout_seconds = 120
    copilot_model_cheap_a = "gpt-5-mini"
    copilot_model_cheap_b = "gpt-4.1"
    copilot_model_plan = "claude-haiku-4.5"
    copilot_cli_model_cheap_a = "gpt-5-mini"
    copilot_cli_model_cheap_b = "gpt-4.1"
    copilot_cli_model_plan = "claude-haiku-4.5"


def test_codex_adapter_uses_exec_when_no_command(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/codex")
    executor = _FakeExecutor()
    adapter = CliAIAgentAdapter("codex", "codex", executor)
    req = AdapterRequest(
        objective="Create a small UI component",
        command=None,
        cwd="/tmp/demo",
        timeout_seconds=120,
        rendered_context={"sections": {"constraints": "keep it simple"}, "repo_context": {"writable_roots": ["/tmp/demo"]}},
        selected_profile="codex_iterative",
        provider_model_alias="gpt-5.1-codex",
    )

    result = adapter.execute(req)

    assert result.ok is True
    assert executor.last_command[0:2] == ["codex", "exec"]
    assert "--full-auto" in executor.last_command
    assert "--sandbox" in executor.last_command
    assert "workspace-write" in executor.last_command
    assert "--model" in executor.last_command
    assert "gpt-5.1-codex" in executor.last_command
    assert executor.last_env["HOME"] == os.environ.get("HOME", "/root")
    assert executor.last_env["CODEX_HOME"] == os.environ.get("CODEX_HOME", f"{executor.last_env['HOME']}/.codex")


def test_copilot_adapter_uses_allowed_alias(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/copilot")
    executor = _FakeExecutor()
    adapter = CopilotAdapter("copilot", executor, _FakeCopilotSettings())
    req = AdapterRequest(
        objective="small fix",
        command=None,
        cwd="/tmp/demo",
        timeout_seconds=120,
        rendered_context={"sections": {}, "repo_context": {"writable_roots": ["/tmp/demo"]}},
        selected_profile="copilot_cheap_b",
        provider_model_alias="gpt-4.1",
    )

    result = adapter.execute(req)

    assert result.ok is True
    assert "--model" in executor.last_command
    model_index = executor.last_command.index("--model") + 1
    assert executor.last_command[model_index] == "gpt-4.1"


def test_copilot_adapter_rejects_unknown_alias_and_falls_back(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/copilot")
    executor = _FakeExecutor()
    adapter = CopilotAdapter("copilot", executor, _FakeCopilotSettings())
    req = AdapterRequest(
        objective="plan change",
        command=None,
        cwd="/tmp/demo",
        timeout_seconds=120,
        rendered_context={"sections": {}, "repo_context": {"writable_roots": ["/tmp/demo"]}},
        selected_profile="copilot_plan",
        provider_model_alias="claude-sonnet-4.6",
    )

    result = adapter.execute(req)

    assert result.ok is True
    assert "--model" in executor.last_command
    model_index = executor.last_command.index("--model") + 1
    assert executor.last_command[model_index] == "claude-haiku-4.5"

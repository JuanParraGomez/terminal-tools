from __future__ import annotations

from app.adapters.base import BaseAdapter
from app.adapters.cli_ai_adapter import CliAIAgentAdapter
from app.adapters.gcloud_adapter import GCloudAdapter
from app.adapters.terminal_adapter import TerminalAdapter
from app.core.settings import Settings
from app.services.executor import CommandExecutor


class AdapterRegistry:
    def __init__(self, settings: Settings, executor: CommandExecutor) -> None:
        self._adapters: dict[str, BaseAdapter] = {
            "terminal": TerminalAdapter(executor),
            "copilot": CliAIAgentAdapter("copilot", settings.copilot_bin, executor),
            "claude": CliAIAgentAdapter("claude", settings.claude_bin, executor),
            "codex": CliAIAgentAdapter("codex", settings.codex_bin, executor),
            "gcloud": GCloudAdapter(settings.gcloud_bin, executor),
            "gemini_cli": CliAIAgentAdapter("gemini_cli", settings.gemini_cli_bin, executor),
        }

    def get(self, name: str) -> BaseAdapter:
        adapter = self._adapters.get(name)
        if not adapter:
            raise ValueError(f"adapter '{name}' not found")
        return adapter

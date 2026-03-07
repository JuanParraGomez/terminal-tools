from __future__ import annotations

from app.adapters.base import BaseAdapter
from app.adapters.cli_ai_adapter import CliAIAgentAdapter
from app.adapters.copilot_adapter import CopilotAdapter
from app.adapters.gcloud_adapter import GCloudAdapter
from app.adapters.langgraph_delegate_adapter import LanggraphDelegateAdapter
from app.adapters.terminal_adapter import TerminalAdapter
from app.core.settings import Settings
from app.services.executor import CommandExecutor
from app.services.langgraph_service import LanggraphService


class AdapterRegistry:
    def __init__(self, settings: Settings, executor: CommandExecutor, langgraph_service: LanggraphService) -> None:
        self._adapters: dict[str, BaseAdapter] = {
            "terminal": TerminalAdapter(executor),
            "copilot": CopilotAdapter(settings.copilot_bin, executor, settings),
            "claude": CliAIAgentAdapter("claude", settings.claude_bin, executor),
            "codex": CliAIAgentAdapter("codex", settings.codex_bin, executor),
            "gcloud": GCloudAdapter(settings.gcloud_bin, executor),
            "gemini_cli": CliAIAgentAdapter("gemini_cli", settings.gemini_cli_bin, executor),
            "langgraph_agent_server": LanggraphDelegateAdapter(langgraph_service),
        }

    def get(self, name: str) -> BaseAdapter:
        adapter = self._adapters.get(name)
        if not adapter:
            raise ValueError(f"adapter '{name}' not found")
        return adapter

from __future__ import annotations

from pathlib import Path

from app.adapters.base import AdapterRequest, AdapterResponse, BaseAdapter
from app.services.executor import CommandExecutor


class TerminalAdapter(BaseAdapter):
    name = "terminal"

    def __init__(self, executor: CommandExecutor) -> None:
        self.executor = executor

    def execute(self, req: AdapterRequest) -> AdapterResponse:
        if not req.command:
            return AdapterResponse(ok=False, summary="No command provided", result={"error": "missing command"}, used_context_sections=[])
        result = self.executor.run(req.command, cwd=Path(req.cwd) if req.cwd else None, timeout_seconds=req.timeout_seconds)
        return AdapterResponse(
            ok=bool(result.get("ok")),
            summary="Command executed" if result.get("ok") else "Command failed",
            result=result,
            used_context_sections=list(req.rendered_context.get("sections", {}).keys()),
        )

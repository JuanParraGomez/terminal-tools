from __future__ import annotations

import shutil
from pathlib import Path

from app.adapters.base import AdapterRequest, AdapterResponse, BaseAdapter
from app.services.executor import CommandExecutor


class CliAIAgentAdapter(BaseAdapter):
    def __init__(self, name: str, binary: str, executor: CommandExecutor) -> None:
        self.name = name
        self.binary = binary
        self.executor = executor

    def execute(self, req: AdapterRequest) -> AdapterResponse:
        if not shutil.which(self.binary):
            return AdapterResponse(
                ok=False,
                summary=f"{self.name} unavailable",
                result={"error": f"binary '{self.binary}' not found"},
                used_context_sections=list(req.rendered_context.get("sections", {}).keys()),
            )

        cmd = req.command or [self.binary, "--version"]
        result = self.executor.run(cmd, cwd=Path(req.cwd) if req.cwd else None, timeout_seconds=req.timeout_seconds)
        return AdapterResponse(
            ok=bool(result.get("ok")),
            summary=f"{self.name} task executed" if result.get("ok") else f"{self.name} task failed",
            result={
                **result,
                "objective": req.objective,
                "context_text": self._render_text(req),
            },
            used_context_sections=list(req.rendered_context.get("sections", {}).keys()),
        )

    def _render_text(self, req: AdapterRequest) -> str:
        lines = [f"Objective: {req.objective}", f"Tool: {self.name}"]
        sections = req.rendered_context.get("sections", {})
        for k, v in sections.items():
            lines.append(f"{k}: {v}")
        return "\n".join(lines)

from __future__ import annotations

import shutil
from pathlib import Path

from app.adapters.base import AdapterRequest, AdapterResponse, BaseAdapter
from app.services.executor import CommandExecutor


class GCloudAdapter(BaseAdapter):
    name = "gcloud"

    def __init__(self, binary: str, executor: CommandExecutor) -> None:
        self.binary = binary
        self.executor = executor

    def execute(self, req: AdapterRequest) -> AdapterResponse:
        if not shutil.which(self.binary):
            return AdapterResponse(ok=False, summary="gcloud unavailable", result={"error": "gcloud not found"}, used_context_sections=list(req.rendered_context.get("sections", {}).keys()))

        cmd = req.command or [self.binary, "info", "--format=json"]
        result = self.executor.run(cmd, cwd=Path(req.cwd) if req.cwd else None, timeout_seconds=req.timeout_seconds)
        return AdapterResponse(
            ok=bool(result.get("ok")),
            summary="gcloud command executed" if result.get("ok") else "gcloud command failed",
            result=result,
            used_context_sections=list(req.rendered_context.get("sections", {}).keys()),
        )

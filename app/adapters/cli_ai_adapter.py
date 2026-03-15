from __future__ import annotations

import json
import os
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

        cwd = Path(req.cwd) if req.cwd else None
        cmd = req.command or self._default_command(req)
        result = self.executor.run(
            cmd,
            cwd=cwd,
            timeout_seconds=req.timeout_seconds,
            env=self._runtime_env(),
        )
        return AdapterResponse(
            ok=bool(result.get("ok")),
            summary=f"{self.name} task executed" if result.get("ok") else f"{self.name} task failed",
            result={
                **result,
                "objective": req.objective,
                "context_text": self._render_text(req),
                "effective_command": cmd,
            },
            used_context_sections=list(req.rendered_context.get("sections", {}).keys()),
        )

    def _default_command(self, req: AdapterRequest) -> list[str]:
        if self.name == "codex":
            return self._codex_exec_command(req)
        if self.name == "claude":
            return self._claude_exec_command(req)
        return [self.binary, "--version"]

    def _claude_exec_command(self, req: AdapterRequest) -> list[str]:
        prompt = self._render_text(req)
        model = req.provider_model_alias or "claude-haiku-4-5"
        cmd = [
            self.binary,
            "--print",
            prompt,
            "--model",
            model,
            "--output-format",
            "text",
            "--dangerously-skip-permissions",
        ]
        if req.cwd:
            cmd.extend(["--add-dir", req.cwd])
        return cmd

    def _codex_exec_command(self, req: AdapterRequest) -> list[str]:
        prompt = self._render_text(req)
        # Use repo_root as cwd so git commands run from the repo root, not a subdir
        repo_root = req.rendered_context.get("repo_context", {}).get("repo_root")
        effective_cwd = repo_root or req.cwd
        cmd = [
            self.binary,
            "exec",
            prompt,
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--full-auto",
            "--json",
        ]
        if effective_cwd:
            cmd.extend(["-C", effective_cwd])
        for allowed_dir in self._allowed_dirs(req, req.cwd):
            cmd.extend(["--add-dir", allowed_dir])
        if req.provider_model_alias:
            cmd.extend(["--model", req.provider_model_alias])
        return cmd

    def _render_text(self, req: AdapterRequest) -> str:
        lines = [f"Objective: {req.objective}", f"Tool: {self.name}"]
        sections = req.rendered_context.get("sections", {})
        for k, v in sections.items():
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=True) if isinstance(v, (dict, list)) else v}")
        repo_context = req.rendered_context.get("repo_context", {})
        if repo_context:
            lines.append(f"RepoContext: {json.dumps(repo_context, ensure_ascii=True)}")
        if self.name == "codex":
            lines.extend(
                [
                    "ExecutionMode: apply_changes",
                    "Modify files only inside the allowed repo roots.",
                    "Run the smallest useful validation before finishing.",
                    "At the end, summarize changed files and remaining risks.",
                ]
            )
        if self.name == "claude" and req.selected_profile in {"claude_plan", "claude_code"}:
            lines.extend(
                [
                    "ExecutionMode: apply_changes",
                    "Apply all required file changes directly using your file editing tools.",
                    "Modify only files inside the allowed repo roots.",
                    "Run the smallest useful validation after applying changes.",
                    "At the end, summarize changed files and remaining risks.",
                ]
            )
        return "\n".join(lines)

    def _allowed_dirs(self, req: AdapterRequest, cwd: str | None) -> list[str]:
        roots = req.rendered_context.get("repo_context", {}).get("writable_roots", []) or []
        items = [str(item) for item in roots if item]
        if cwd and cwd not in items:
            items.append(cwd)
        deduped: list[str] = []
        for item in items:
            if item not in deduped:
                deduped.append(item)
        return deduped

    def _runtime_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        if self.name == "codex":
            env["HOME"] = os.environ.get("HOME", "/root")
            env["CODEX_HOME"] = os.environ.get("CODEX_HOME", f"{env['HOME']}/.codex")
        elif self.name == "copilot":
            env["HOME"] = os.environ.get("HOME", "/root")
        return env

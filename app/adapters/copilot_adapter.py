from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.adapters.base import AdapterRequest, AdapterResponse, BaseAdapter
from app.core.settings import Settings
from app.services.executor import CommandExecutor


class CopilotAdapter(BaseAdapter):
    name = "copilot"

    def __init__(self, binary: str, executor: CommandExecutor, settings: Settings) -> None:
        self.binary = binary
        self.executor = executor
        self.settings = settings

    def execute(self, req: AdapterRequest) -> AdapterResponse:
        if not shutil.which(self.binary):
            return AdapterResponse(
                ok=False,
                summary="copilot unavailable",
                result={"error": f"binary '{self.binary}' not found"},
                used_context_sections=list(req.rendered_context.get("sections", {}).keys()),
            )

        cwd = self._resolve_cwd(req)
        cli_model = self._resolve_cli_model(req)
        prompt = self._build_prompt(req)
        command = [self.binary, "-p", prompt, "--output-format", "text", "--allow-all-tools", "--no-color"]
        for allowed_dir in self._allowed_dirs(req, cwd):
            command.extend(["--add-dir", allowed_dir])
        if cli_model:
            command.extend(["--model", cli_model])

        result = self.executor.run(command, cwd=Path(cwd) if cwd else None, timeout_seconds=req.timeout_seconds or self.settings.default_timeout_seconds)
        result["copilot_profile"] = req.selected_profile
        result["copilot_model_alias"] = req.provider_model_alias or self._alias_for_profile(req.selected_profile)
        result["copilot_cli_model"] = cli_model
        result["effective_cwd"] = cwd
        return AdapterResponse(
            ok=bool(result.get("ok")),
            summary="copilot task executed" if result.get("ok") else "copilot task failed",
            result=result,
            used_context_sections=list(req.rendered_context.get("sections", {}).keys()),
        )

    def _resolve_cwd(self, req: AdapterRequest) -> str | None:
        if req.cwd:
            return req.cwd
        repo_root = req.rendered_context.get("repo_context", {}).get("repo_root")
        return str(repo_root) if repo_root else None

    def _allowed_dirs(self, req: AdapterRequest, cwd: str | None) -> list[str]:
        roots = req.rendered_context.get("repo_context", {}).get("writable_roots", []) or []
        items = [str(item) for item in roots if item]
        if cwd and cwd not in items:
            items.append(cwd)
        if not items and cwd:
            items.append(cwd)
        deduped: list[str] = []
        for item in items:
            if item not in deduped:
                deduped.append(item)
        return deduped

    def _resolve_cli_model(self, req: AdapterRequest) -> str | None:
        requested = (req.provider_model_alias or "").strip()
        if requested:
            if requested in {self.settings.copilot_model_cheap_a, self.settings.copilot_model_cheap_b, self.settings.copilot_model_plan}:
                return self._cli_model_for_alias(requested)
            return requested
        return self._cli_model_for_alias(self._alias_for_profile(req.selected_profile))

    def _alias_for_profile(self, profile: str | None) -> str:
        if profile == "copilot_cheap_b":
            return self.settings.copilot_model_cheap_b
        if profile == "copilot_plan":
            return self.settings.copilot_model_plan
        return self.settings.copilot_model_cheap_a

    def _cli_model_for_alias(self, alias: str) -> str | None:
        if alias == self.settings.copilot_model_cheap_a:
            return self.settings.copilot_cli_model_cheap_a
        if alias == self.settings.copilot_model_cheap_b:
            return self.settings.copilot_cli_model_cheap_b
        if alias == self.settings.copilot_model_plan:
            return self.settings.copilot_cli_model_plan
        return None

    def _build_prompt(self, req: AdapterRequest) -> str:
        sections = req.rendered_context.get("sections", {})
        repo_context = req.rendered_context.get("repo_context", {})
        profile = req.selected_profile or "copilot_cheap_a"
        lines = [
            f"Profile: {profile}",
            f"Objective: {req.objective}",
        ]
        if repo_context:
            lines.append(f"RepoContext: {json.dumps(repo_context, ensure_ascii=True)}")
        if sections:
            lines.append(f"ContextSections: {json.dumps(sections, ensure_ascii=True)}")

        if profile == "copilot_plan":
            lines.extend(
                [
                    "TaskMode: plan_only",
                    "Do not modify files.",
                    "Return a concrete implementation plan for the code task, impacted files, validation steps, rollback notes, and risks.",
                ]
            )
        else:
            lines.extend(
                [
                    "TaskMode: coding",
                    "Prefer the smallest correct code change.",
                    "If you edit files, stay within the allowed repo roots and mention validation steps.",
                ]
            )
        return "\n".join(lines)

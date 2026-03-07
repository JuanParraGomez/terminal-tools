from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.settings import Settings
from app.security.path_policy_service import PathPolicyService
from app.security.validator import SecurityError, SecurityValidator
from app.services.executor import CommandExecutor
from app.services.langgraph_service import LanggraphService


class RepoOpsService:
    def __init__(
        self,
        settings: Settings,
        validator: SecurityValidator,
        path_policy: PathPolicyService,
        executor: CommandExecutor,
        langgraph_service: LanggraphService,
    ) -> None:
        self.settings = settings
        self.validator = validator
        self.path_policy = path_policy
        self.executor = executor
        self.langgraph_service = langgraph_service

    @property
    def repo_root(self) -> Path:
        return self.settings.langgraph_agent_repo_root.resolve()

    @property
    def repo_tests_root(self) -> Path:
        return self.settings.langgraph_agent_repo_tests_dir.resolve()

    def list_repo_structure(self, max_depth: int = 3, include_hidden: bool = False) -> dict[str, Any]:
        root = self.repo_root
        check = self.path_policy.evaluate(root, "read")
        if not check.allowed:
            raise SecurityError(f"repo root blocked: {check.reason}")

        items: list[dict[str, Any]] = []
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            depth = len(rel.parts)
            if depth > max_depth:
                continue
            if not include_hidden and any(part.startswith(".") for part in rel.parts):
                continue
            # Skip blocked paths explicitly.
            action = "read"
            decision = self.path_policy.evaluate(path, action)
            if not decision.allowed:
                continue
            items.append({"path": str(rel), "type": "dir" if path.is_dir() else "file", "depth": depth})
        return {"repo_root": str(root), "max_depth": max_depth, "items": items}

    def run_repo_tests(self, pytest_args: list[str] | None = None, timeout_seconds: int | None = 300) -> dict[str, Any]:
        root = self.repo_root
        self.validator.validate_cwd(root)
        args = pytest_args or ["-q"]
        command = ["python3", "-m", "pytest", *args]
        self.validator.validate_command(command, root, allow_mutative=False)
        result = self.executor.run(command, cwd=root, timeout_seconds=timeout_seconds)
        return {
            "ok": bool(result.get("ok")),
            "command": command,
            "cwd": str(root),
            "returncode": int(result.get("returncode", 1)),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        }

    def edit_repo_file(self, relative_path: str, content: str, mode: str = "overwrite", create_dirs: bool = True) -> dict[str, Any]:
        target = (self.repo_root / relative_path).resolve()

        if not str(target).startswith(str(self.repo_root)):
            raise SecurityError("path escapes repo root")

        exists = target.exists()
        if exists:
            write_decision = self.path_policy.evaluate(target, "write")
            if not write_decision.allowed:
                raise SecurityError(f"write blocked: {write_decision.reason}")
        else:
            create_decision = self.path_policy.evaluate(target, "create_file")
            if not create_decision.allowed:
                raise SecurityError(f"create_file blocked: {create_decision.reason}")

        if create_dirs and not target.parent.exists():
            parent_decision = self.path_policy.evaluate(target.parent, "create_dir")
            if not parent_decision.allowed:
                raise SecurityError(f"create_dir blocked: {parent_decision.reason}")
            target.parent.mkdir(parents=True, exist_ok=True)

        if mode == "create" and target.exists():
            raise SecurityError("file already exists and mode=create")

        if mode == "append":
            before = target.read_text(encoding="utf-8") if target.exists() else ""
            text = before + content
        else:
            text = content

        target.write_text(text, encoding="utf-8")

        return {
            "ok": True,
            "path": str(target),
            "mode": mode,
            "bytes_written": len(content.encode("utf-8")),
        }

    def get_langgraph_capabilities(self) -> dict[str, Any]:
        return self.langgraph_service.capabilities()

    def delegate_complex_task(self, user_goal: str, context: dict[str, Any], max_iterations: int) -> dict[str, Any]:
        return self.langgraph_service.delegate_complex_task(user_goal=user_goal, context=context, max_iterations=max_iterations)

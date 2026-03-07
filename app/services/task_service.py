from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.adapters.base import AdapterRequest
from app.adapters.router import AdapterRegistry
from app.core.settings import Settings
from app.models.schemas import (
    GoogleCliTaskRequest,
    RouteDecision,
    RouteTaskRequest,
    RunCommandRequest,
    RunScriptRequest,
    TaskResponse,
    ToolTaskRequest,
)
from app.routing.router import RoutingService
from app.security.path_policy_service import PathPolicyService
from app.security.validator import SecurityError, SecurityValidator
from app.services.context_service import ContextService
from app.services.recipe_service import RecipeService
from app.services.trash_service import TrashService
from app.storage.db import Database


class TaskService:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        context_service: ContextService,
        routing_service: RoutingService,
        validator: SecurityValidator,
        adapters: AdapterRegistry,
        recipes: RecipeService,
        path_policy: PathPolicyService,
        trash_service: TrashService,
    ) -> None:
        self.settings = settings
        self.db = db
        self.context_service = context_service
        self.routing_service = routing_service
        self.validator = validator
        self.adapters = adapters
        self.recipes = recipes
        self.path_policy = path_policy
        self.trash_service = trash_service

    def route(self, request: RouteTaskRequest) -> RouteDecision:
        snapshot = self.context_service.get_context(refresh=False)
        available = set(snapshot.get("available_tools", []))
        return self.routing_service.decide(request, available)

    def run_command(self, request: RunCommandRequest) -> TaskResponse:
        decision = RouteDecision(
            selected_tool="terminal",
            selected_profile="terminal_safe",
            reasoning_short="Direct command execution",
            execution_mode=request.execution_mode,
            requires_context_sections=["security", "workdirs", "scripts"],
        )
        return self._dispatch(
            decision=decision,
            objective=request.user_goal,
            command=request.command,
            cwd=request.cwd,
            timeout=request.timeout_seconds,
            allow_mutative=request.allow_mutative,
            execution_mode=request.execution_mode,
        )

    def run_script(self, request: RunScriptRequest) -> TaskResponse:
        script = Path(request.script_path)
        self.validator.validate_script_path(script, allow_mutative=request.allow_mutative)
        command = ["bash", str(script)] + request.args
        decision = RouteDecision(
            selected_tool="terminal",
            selected_profile="terminal_script",
            reasoning_short="Allowed script execution",
            execution_mode=request.execution_mode,
            requires_context_sections=["security", "scripts", "workdirs"],
        )
        return self._dispatch(
            decision=decision,
            objective=request.user_goal,
            command=command,
            cwd=request.cwd,
            timeout=request.timeout_seconds,
            allow_mutative=request.allow_mutative,
            execution_mode=request.execution_mode,
        )

    def run_tool_task(self, tool: str, request: ToolTaskRequest, default_profile: str) -> TaskResponse:
        decision = RouteDecision(
            selected_tool=tool,  # type: ignore[arg-type]
            selected_profile=default_profile,
            reasoning_short=f"Direct {tool} execution",
            execution_mode=request.execution_mode,
            requires_context_sections=["repos", "git_status", "constraints"] if tool in {"claude", "codex", "copilot"} else ["security", "workdirs"],
        )
        return self._dispatch(
            decision=decision,
            objective=request.user_goal,
            command=None,
            cwd=request.cwd,
            timeout=request.timeout_seconds,
            allow_mutative=False,
            execution_mode=request.execution_mode,
            provider_model_alias=request.provider_model_alias,
        )

    def run_google_cli(self, request: GoogleCliTaskRequest) -> TaskResponse:
        command = request.command
        if request.recipe:
            command = self.recipes.render_command(request.recipe, request.recipe_args)
        if not command:
            raise ValueError("command or recipe is required")

        decision = RouteDecision(
            selected_tool="gcloud",
            selected_profile="google-readonly",
            reasoning_short="Google CLI task",
            execution_mode=request.execution_mode,
            requires_context_sections=["google_context", "recipes", "commands"],
        )
        return self._dispatch(
            decision=decision,
            objective=request.user_goal,
            command=command,
            cwd=request.cwd,
            timeout=request.timeout_seconds,
            allow_mutative=request.allow_mutative,
            execution_mode=request.execution_mode,
        )

    def run_routed(self, request: RouteTaskRequest, execution_mode: str = "sync") -> TaskResponse:
        decision = self.route(request)
        return self._dispatch(
            decision=decision,
            objective=request.user_goal,
            command=None,
            cwd=None,
            timeout=None,
            allow_mutative=request.allowed_mutation_level != "readonly",
            execution_mode=execution_mode,
            provider_model_alias=None,
        )

    def get_task(self, task_id: str) -> TaskResponse:
        item = self.db.get_task(task_id)
        if not item:
            raise ValueError("task not found")
        return self._to_response(item)

    def list_tasks(self, limit: int = 50) -> list[TaskResponse]:
        return [self._to_response(item) for item in self.db.list_tasks(limit=limit)]

    def get_logs(self, task_id: str) -> tuple[str, str]:
        item = self.db.get_task(task_id)
        if not item:
            raise ValueError("task not found")
        stdout = ""
        stderr = ""
        if item.get("stdout_path") and Path(item["stdout_path"]).exists():
            out_decision = self.path_policy.evaluate(Path(item["stdout_path"]), "read")
            if not out_decision.allowed:
                raise ValueError(f"log read blocked by policy: {out_decision.reason}")
            stdout = Path(item["stdout_path"]).read_text(encoding="utf-8")
        if item.get("stderr_path") and Path(item["stderr_path"]).exists():
            err_decision = self.path_policy.evaluate(Path(item["stderr_path"]), "read")
            if not err_decision.allowed:
                raise ValueError(f"log read blocked by policy: {err_decision.reason}")
            stderr = Path(item["stderr_path"]).read_text(encoding="utf-8")
        return stdout, stderr

    def create_session(self, name: str | None, metadata: dict) -> dict:
        return self.db.create_session(session_id=f"sess_{uuid4().hex[:12]}", name=name, metadata=metadata)

    def get_session(self, session_id: str) -> dict:
        item = self.db.get_session(session_id)
        if not item:
            raise ValueError("session not found")
        return item

    def _dispatch(
        self,
        decision: RouteDecision,
        objective: str,
        command: list[str] | None,
        cwd: str | None,
        timeout: int | None,
        allow_mutative: bool,
        execution_mode: str,
        provider_model_alias: str | None = None,
    ) -> TaskResponse:
        snapshot = self.context_service.get_context(refresh=False)
        task_id = f"task_{uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()

        row = {
            "task_id": task_id,
            "created_at": created_at,
            "status": "pending",
            "selected_tool": decision.selected_tool,
            "selected_profile": decision.selected_profile,
            "input_summary": objective[:240],
            "cwd": cwd,
            "command": command,
            "result": {},
            "stdout_path": str(self.settings.logs_dir / f"{task_id}.out.log"),
            "stderr_path": str(self.settings.logs_dir / f"{task_id}.err.log"),
            "summary": None,
            "error": None,
            "context_id": snapshot["context_id"],
            "context_freshness": self._context_freshness(snapshot["created_at"]),
            "used_context_sections": decision.requires_context_sections,
        }
        self.db.upsert_task(row)
        trash_scope = "langgraph_agent_server" if self._prefer_langgraph_repo(cwd, objective, decision.selected_tool) else None
        self.trash_service.create_space(task_id=task_id, label="task-artifacts", scope=trash_scope)

        if execution_mode == "async":
            thread = threading.Thread(
                target=self._run_task,
                kwargs={
                    "row": row,
                    "objective": objective,
                    "command": command,
                    "cwd": cwd,
                    "timeout": timeout,
                    "allow_mutative": allow_mutative,
                    "decision": decision,
                    "snapshot": snapshot,
                },
                daemon=True,
            )
            thread.start()
            return self._to_response(row)

        done = self._run_task(
            row=row,
            objective=objective,
            command=command,
            cwd=cwd,
            timeout=timeout,
            allow_mutative=allow_mutative,
            decision=decision,
            snapshot=snapshot,
        )
        return self._to_response(done)

    def _run_task(
        self,
        row: dict,
        objective: str,
        command: list[str] | None,
        cwd: str | None,
        timeout: int | None,
        allow_mutative: bool,
        decision: RouteDecision,
        snapshot: dict,
    ) -> dict:
        row["status"] = "running"
        row["started_at"] = datetime.now(timezone.utc).isoformat()
        self.db.upsert_task(row)

        try:
            if command is not None:
                self.validator.validate_command(command, Path(cwd) if cwd else None, allow_mutative=allow_mutative)

            rendered = self.context_service.render_for_tool(
                snapshot=snapshot,
                selected_tool=decision.selected_tool,
                sections=decision.requires_context_sections,
                objective=objective,
            )
            preferred_root = str(self.settings.langgraph_agent_repo_root.resolve()) if self._prefer_langgraph_repo(cwd, objective, decision.selected_tool) else None
            rendered["path_policy_summary"] = self.path_policy.render_summary_for_context(task_id=row["task_id"], preferred_root=preferred_root)
            if preferred_root:
                rendered["scratch_root"] = str(self.settings.langgraph_agent_repo_trash_dir / f"task_{row['task_id']}")
            else:
                rendered["scratch_root"] = str(self.settings.trash_dir / f"task_{row['task_id']}")
            rendered["repo_context"] = {
                "repo_root": str(self.settings.langgraph_agent_repo_root.resolve()),
                "recommended_dirs": ["app/agents", "app/graphs", "tests"],
                "writable_roots": [
                    str(self.settings.langgraph_agent_repo_root.resolve()),
                    str(self.settings.langgraph_agent_repo_tests_dir.resolve()),
                ],
                "scratch_root": rendered["scratch_root"],
            }
            rendered["delegation_options"] = {
                "langgraph_agent_server_available": bool(snapshot.get("langgraph_agent_server", {}).get("available", False))
            }
            req = AdapterRequest(
                objective=objective,
                command=command,
                cwd=cwd,
                timeout_seconds=timeout,
                rendered_context=rendered,
                selected_profile=decision.selected_profile,
                provider_model_alias=provider_model_alias,
            )
            adapter = self.adapters.get(decision.selected_tool)
            output = adapter.execute(req)
            result = output.result

            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            out_decision = self.path_policy.evaluate(Path(row["stdout_path"]), "create_file")
            err_decision = self.path_policy.evaluate(Path(row["stderr_path"]), "create_file")
            if not out_decision.allowed or not err_decision.allowed:
                raise SecurityError("path policy denied writing task logs")
            Path(row["stdout_path"]).write_text(stdout, encoding="utf-8")
            Path(row["stderr_path"]).write_text(stderr, encoding="utf-8")

            row["status"] = "succeeded" if output.ok else "failed"
            row["result"] = result
            row["summary"] = output.summary
            row["used_context_sections"] = output.used_context_sections
        except SecurityError as exc:
            Path(row["stderr_path"]).write_text(str(exc), encoding="utf-8")
            row["status"] = "failed"
            row["error"] = str(exc)
            row["summary"] = "Security validation failed"
        except Exception as exc:
            Path(row["stderr_path"]).write_text(str(exc), encoding="utf-8")
            row["status"] = "failed"
            row["error"] = str(exc)
            row["summary"] = "Execution failed"
        finally:
            row["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.db.upsert_task(row)

        return row

    def _prefer_langgraph_repo(self, cwd: str | None, objective: str, selected_tool: str) -> bool:
        if selected_tool == "langgraph_agent_server":
            return True
        if "langgraph-agent-server" in objective.lower():
            return True
        if cwd:
            cwd_path = Path(cwd).expanduser().resolve()
            try:
                cwd_path.relative_to(self.settings.langgraph_agent_repo_root.resolve())
                return True
            except ValueError:
                return False
        return False

    def _context_freshness(self, created_at: str) -> str:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(created_at)).total_seconds()
        return "stale" if age > self.settings.context_ttl_seconds else "fresh"

    @staticmethod
    def _to_response(item: dict) -> TaskResponse:
        return TaskResponse(
            task_id=item["task_id"],
            status=item["status"],
            selected_tool=item["selected_tool"],
            selected_profile=item["selected_profile"],
            created_at=datetime.fromisoformat(item["created_at"]),
            started_at=datetime.fromisoformat(item["started_at"]) if item.get("started_at") else None,
            finished_at=datetime.fromisoformat(item["finished_at"]) if item.get("finished_at") else None,
            summary=item.get("summary"),
            error=item.get("error"),
            cwd=item.get("cwd"),
            command=item.get("command"),
            result=item.get("result") or {},
            stdout_path=item.get("stdout_path"),
            stderr_path=item.get("stderr_path"),
            context_id=item.get("context_id"),
            context_freshness=item.get("context_freshness"),
            used_context_sections=item.get("used_context_sections") or [],
        )

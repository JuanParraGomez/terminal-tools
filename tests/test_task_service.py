from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.models.schemas import RouteDecision, ToolTaskRequest
from app.services.task_service import TaskService


class _FakeDB:
    def __init__(self) -> None:
        self.tasks: dict[str, dict] = {}

    def upsert_task(self, row: dict) -> None:
        self.tasks[row["task_id"]] = dict(row)

    def get_task(self, task_id: str) -> dict | None:
        return self.tasks.get(task_id)

    def list_tasks(self, limit: int = 50) -> list[dict]:
        return list(self.tasks.values())[:limit]

    def create_session(self, session_id: str, name: str | None, metadata: dict) -> dict:
        return {"session_id": session_id, "created_at": datetime.now(timezone.utc).isoformat(), "name": name, "metadata": metadata}

    def get_session(self, session_id: str) -> dict | None:
        return None


class _FakeContextService:
    def get_context(self, refresh: bool = False) -> dict:
        return {
            "context_id": "ctx_test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "available_tools": ["copilot"],
            "langgraph_agent_server": {"available": False},
        }

    def render_for_tool(self, snapshot: dict, selected_tool: str, sections: list[str], objective: str) -> dict:
        return {"sections": {section: f"section:{section}" for section in sections}}


class _FakeValidator:
    def validate_command(self, command: list[str], cwd: Path | None, allow_mutative: bool) -> None:
        return None

    def validate_script_path(self, script_path: Path, allow_mutative: bool) -> None:
        return None


class _FakePathPolicy:
    def evaluate(self, path: Path | str, action: str):
        from app.models.schemas import PathAccessCheckResponse

        return PathAccessCheckResponse(
            path=str(path),
            action=action,
            resolved_permission="read_write",
            allowed=True,
            matched_rule=None,
            reason="allowed in test",
        )

    def render_summary_for_context(self, task_id: str | None = None, preferred_root: str | None = None) -> dict:
        return {"read_write_roots": [], "scratch_root": None, "scratch_roots": [], "blocked_patterns": []}


class _FakeTrashService:
    def create_space(self, task_id: str, label: str | None = None, scope: str | None = None) -> dict:
        return {"task_id": task_id, "scope": scope}


class _CapturingAdapter:
    def __init__(self) -> None:
        self.last_request = None

    def execute(self, req):
        self.last_request = req
        from app.adapters.base import AdapterResponse

        return AdapterResponse(
            ok=True,
            summary="ok",
            result={"ok": True, "stdout": "done", "stderr": ""},
            used_context_sections=["repos"],
        )


class _FakeAdapters:
    def __init__(self, adapter) -> None:
        self.adapter = adapter

    def get(self, name: str):
        return self.adapter


class _FakeSettings:
    def __init__(self, tmp_path: Path) -> None:
        self.logs_dir = tmp_path / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.context_ttl_seconds = 900
        self.langgraph_agent_repo_root = tmp_path / "langgraph-agent-server"
        self.langgraph_agent_repo_root.mkdir(parents=True, exist_ok=True)
        self.langgraph_agent_repo_tests_dir = self.langgraph_agent_repo_root / "tests"
        self.langgraph_agent_repo_tests_dir.mkdir(parents=True, exist_ok=True)
        self.langgraph_agent_repo_trash_dir = self.langgraph_agent_repo_root / "data" / "trash"
        self.langgraph_agent_repo_trash_dir.mkdir(parents=True, exist_ok=True)
        self.trash_dir = tmp_path / "trash"
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        self.copilot_model_cheap_a = "gpt-5-mini"
        self.copilot_model_cheap_b = "gpt-4.1"
        self.copilot_model_plan = "claude-haiku-4.5"
        self.claude_model_review = "claude-haiku-4.5"


def test_run_tool_task_passes_provider_model_alias(tmp_path: Path) -> None:
    adapter = _CapturingAdapter()
    service = TaskService(
        settings=_FakeSettings(tmp_path),
        db=_FakeDB(),
        context_service=_FakeContextService(),
        routing_service=None,  # type: ignore[arg-type]
        validator=_FakeValidator(),
        adapters=_FakeAdapters(adapter),
        recipes=None,  # type: ignore[arg-type]
        path_policy=_FakePathPolicy(),
        trash_service=_FakeTrashService(),
    )

    response = service.run_tool_task(
        "copilot",
        ToolTaskRequest(
            user_goal="plan a small code change",
            execution_mode="sync",
            provider_model_alias="gpt-5-mini",
        ),
        default_profile="copilot_plan",
    )

    assert response.status == "succeeded"
    assert adapter.last_request is not None
    assert adapter.last_request.provider_model_alias == "gpt-5-mini"


def test_run_tool_task_forces_cheap_copilot_alias(tmp_path: Path) -> None:
    adapter = _CapturingAdapter()
    service = TaskService(
        settings=_FakeSettings(tmp_path),
        db=_FakeDB(),
        context_service=_FakeContextService(),
        routing_service=None,  # type: ignore[arg-type]
        validator=_FakeValidator(),
        adapters=_FakeAdapters(adapter),
        recipes=None,  # type: ignore[arg-type]
        path_policy=_FakePathPolicy(),
        trash_service=_FakeTrashService(),
    )

    response = service.run_tool_task(
        "copilot",
        ToolTaskRequest(
            user_goal="small fix",
            execution_mode="sync",
            provider_model_alias="claude-sonnet-4.6",
        ),
        default_profile="copilot_plan",
    )

    assert response.status == "succeeded"
    assert adapter.last_request.provider_model_alias == "claude-haiku-4.5"


def test_run_tool_task_forces_claude_haiku(tmp_path: Path) -> None:
    adapter = _CapturingAdapter()
    service = TaskService(
        settings=_FakeSettings(tmp_path),
        db=_FakeDB(),
        context_service=_FakeContextService(),
        routing_service=None,  # type: ignore[arg-type]
        validator=_FakeValidator(),
        adapters=_FakeAdapters(adapter),
        recipes=None,  # type: ignore[arg-type]
        path_policy=_FakePathPolicy(),
        trash_service=_FakeTrashService(),
    )

    response = service.run_tool_task(
        "claude",
        ToolTaskRequest(
            user_goal="review this plan",
            execution_mode="sync",
            provider_model_alias="claude-opus-4.1",
        ),
        default_profile="claude_review",
    )

    assert response.status == "succeeded"
    assert adapter.last_request.provider_model_alias == "claude-haiku-4.5"


def test_run_tool_task_uses_cwd_repo_context(tmp_path: Path) -> None:
    repo_root = tmp_path / "coolify-server"
    project_dir = repo_root / "apps" / "demo-ui"
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)

    adapter = _CapturingAdapter()
    settings = _FakeSettings(tmp_path)
    service = TaskService(
        settings=settings,
        db=_FakeDB(),
        context_service=_FakeContextService(),
        routing_service=None,  # type: ignore[arg-type]
        validator=_FakeValidator(),
        adapters=_FakeAdapters(adapter),
        recipes=None,  # type: ignore[arg-type]
        path_policy=_FakePathPolicy(),
        trash_service=_FakeTrashService(),
    )

    response = service.run_tool_task(
        "copilot",
        ToolTaskRequest(
            user_goal="update the demo ui",
            execution_mode="sync",
            cwd=str(project_dir),
        ),
        default_profile="copilot_cheap_a",
    )

    assert response.status == "succeeded"
    repo_context = adapter.last_request.rendered_context["repo_context"]
    assert repo_context["repo_root"] == str(repo_root)
    assert str(project_dir) in repo_context["writable_roots"]

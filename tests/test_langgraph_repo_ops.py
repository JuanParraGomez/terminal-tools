from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.settings import Settings
from app.security.path_policy_service import PathPolicyService
from app.security.validator import SecurityError
from app.security.validator import SecurityValidator
from app.services.executor import CommandExecutor
from app.services.langgraph_service import LanggraphService
from app.services.repo_ops_service import RepoOpsService
from app.services.trash_service import TrashService


class _FakeLanggraphClient:
    def __init__(self, available: bool = True) -> None:
        self.available = available

    def health(self) -> dict:
        if self.available:
            return {"available": True}
        return {"available": False, "error": "down"}

    def capabilities(self) -> dict:
        if self.available:
            return {"available": True, "data": {"graphs": [{"name": "supervisor_v1"}]}}
        return {"available": False, "error": "down"}

    def run_complex_task(self, user_goal: str, context: dict, max_iterations: int) -> dict:
        return {"run": {"status": "succeeded", "goal": user_goal, "max_iterations": max_iterations}}


def _tmp_policy(tmp_path: Path, repo_root: Path, scratch_root: Path) -> Path:
    policy = tmp_path / "path_policy.yaml"
    policy.write_text(
        f"""
defaults:
  unknown_paths: blocked
  follow_symlinks: false
workspaces:
  - name: langgraph_agent_repo
    root: {repo_root}
    rules:
      - path: {repo_root}
        permission: read_write
        allow_execute: true
        allow_create_files: true
        allow_create_dirs: true
      - path: {repo_root}/tests
        permission: read_write
        allow_execute: true
        allow_create_files: true
        allow_create_dirs: true
      - path: {scratch_root}
        permission: scratch
        allow_execute: true
        allow_create_files: true
        allow_create_dirs: true
        allow_delete: true
        ttl_days: 7
protected:
  - path: {repo_root}/.git
    permission: blocked
  - path: {repo_root}/.git/**
    permission: blocked
    is_pattern: true
  - path: {repo_root}/.env
    permission: blocked
  - path: {repo_root}/**/.env
    permission: blocked
    is_pattern: true
""",
        encoding="utf-8",
    )
    return policy


def _make_repo_ops(tmp_path: Path) -> tuple[RepoOpsService, Path]:
    repo_root = tmp_path / "langgraph-agent-server"
    tests_dir = repo_root / "tests"
    scratch = repo_root / "data" / "trash"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    settings = Settings(
        allowed_workdirs=str(tmp_path),
        langgraph_agent_repo_root=repo_root,
        langgraph_agent_repo_tests_dir=tests_dir,
        langgraph_agent_repo_trash_dir=scratch,
        trash_dir=tmp_path / "default-trash",
    )
    policy = PathPolicyService(_tmp_policy(tmp_path, repo_root, scratch))
    validator = SecurityValidator(
        base_dir=Path(__file__).resolve().parents[1] / "app",
        allowed_workdirs=settings.allowed_workdirs_list,
        allowed_script_dirs=settings.allowed_script_dirs_list,
        path_policy=policy,
    )
    executor = CommandExecutor(default_timeout_seconds=60, max_output_chars=50000)
    langgraph_service = LanggraphService(settings=settings, client=_FakeLanggraphClient(available=True))
    return (
        RepoOpsService(
            settings=settings,
            validator=validator,
            path_policy=policy,
            executor=executor,
            langgraph_service=langgraph_service,
            trash_service=TrashService(settings),
        ),
        repo_root,
    )


def test_langgraph_policy_access_and_blocking(tmp_path: Path) -> None:
    repo_root = tmp_path / "langgraph-agent-server"
    scratch_root = repo_root / "data" / "trash"
    repo_root.mkdir(parents=True, exist_ok=True)
    policy = PathPolicyService(_tmp_policy(tmp_path, repo_root, scratch_root))

    assert policy.evaluate(repo_root, "write").allowed is True
    assert policy.evaluate(repo_root / "tests" / "test_a.py", "create_file").allowed is True
    assert policy.evaluate(repo_root / ".git" / "config", "read").allowed is False
    assert policy.evaluate(repo_root / ".env", "read").allowed is False


def test_trash_scope_langgraph_and_cleanup(tmp_path: Path) -> None:
    settings = Settings(
        trash_dir=tmp_path / "default-trash",
        langgraph_agent_repo_trash_dir=tmp_path / "langgraph-trash",
        trash_ttl_days=7,
    )
    svc = TrashService(settings)

    created = svc.create_space("repo-task", scope="langgraph_agent_server")
    meta_path = Path(created["meta_path"])
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["created_at"] = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    result = svc.cleanup(dry_run=False, ttl_days=7, scope="langgraph_agent_server")
    assert result["scope"] == "langgraph_agent_server"
    assert any("repo-task" in item for item in result["deleted_items"])


def test_run_repo_tests_and_edit(tmp_path: Path) -> None:
    repo_ops, repo_root = _make_repo_ops(tmp_path)
    edited = repo_ops.edit_repo_file("app/agents/new_agent.py", "class NewAgent:\n    pass\n", mode="create")
    assert edited["ok"] is True
    assert (repo_root / "app" / "agents" / "new_agent.py").exists()

    result = repo_ops.run_repo_tests(pytest_args=["-q"], timeout_seconds=120)
    assert result["command"][0:3] == ["python3", "-m", "pytest"]
    assert result["ok"] is True


def test_create_disposable_artifact_goes_to_trash(tmp_path: Path) -> None:
    repo_ops, repo_root = _make_repo_ops(tmp_path)
    created = repo_ops.create_disposable_artifact(
        user_goal="crea un hola mundo temporal para prueba rapida",
        file_name="hello_world.py",
        content="print('hola mundo')\n",
        content_type="code",
    )
    assert created["classified_as_disposable"] is True
    assert "/data/trash/" in created["file_path"]
    assert Path(created["file_path"]).exists()
    assert str(Path(created["file_path"]).parent).startswith(str(repo_root / "data" / "trash"))


def test_non_disposable_artifact_is_rejected(tmp_path: Path) -> None:
    repo_ops, _ = _make_repo_ops(tmp_path)
    try:
        repo_ops.create_disposable_artifact(
            user_goal="crea el agente principal de produccion",
            file_name="core_agent.py",
            content="class CoreAgent:\n    pass\n",
            content_type="code",
        )
    except SecurityError as exc:
        assert "not classified as disposable" in str(exc)
    else:
        raise AssertionError("expected SecurityError")


def test_delegate_complex_task_enabled_and_unavailable_fallback(tmp_path: Path) -> None:
    settings = Settings(enable_langgraph_agent_server=True)
    enabled = LanggraphService(settings=settings, client=_FakeLanggraphClient(available=True))
    delegated = enabled.delegate_complex_task("investiga y sintetiza", context={}, max_iterations=3)
    assert delegated["ok"] is True
    assert delegated["delegated"] is True

    unavailable = LanggraphService(settings=settings, client=_FakeLanggraphClient(available=False))
    fallback = unavailable.delegate_complex_task("investiga y sintetiza", context={}, max_iterations=3)
    assert fallback["ok"] is False
    assert fallback["delegated"] is False

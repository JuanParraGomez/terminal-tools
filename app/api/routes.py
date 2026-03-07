from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.core.settings import get_settings
from app.models.schemas import (
    CapabilitiesResponse,
    CapabilityItem,
    ContextCapabilitiesResponse,
    ContextResponse,
    ContextSnapshot,
    ContextSummary,
    GoogleCliTaskRequest,
    HealthResponse,
    LogsResponse,
    PathAccessCheckRequest,
    PathAccessCheckResponse,
    PathPolicyEffectiveResponse,
    PathPolicySummary,
    ReposResponse,
    RepoEditFileRequest,
    RepoEditFileResponse,
    RepoRunTestsRequest,
    RepoRunTestsResponse,
    RepoStructureRequest,
    RepoStructureResponse,
    RouteDecision,
    RouteTaskRequest,
    RoutedRunRequest,
    RunCommandRequest,
    RunScriptRequest,
    ScriptsResponse,
    SessionCreateRequest,
    SessionResponse,
    TaskListResponse,
    TaskResponse,
    ToolTaskRequest,
    DelegateComplexTaskRequest,
    DelegateComplexTaskResponse,
    LanggraphCapabilitiesResponse,
    TrashCleanupRequest,
    TrashCleanupResponse,
    TrashCreateRequest,
    TrashCreateResponse,
    TrashInfoResponse,
)
from app.services.container import (
    get_context_service,
    get_path_policy_service,
    get_repo_ops_service,
    get_task_service,
    get_trash_service,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    s = get_settings()
    return HealthResponse(status="ok", app=s.app_name, env=s.app_env)


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    snapshot = get_context_service().get_context(refresh=False)
    items = []
    for name, path in snapshot.get("detected_binaries", {}).items():
        items.append(CapabilityItem(name=name, available=True, version=snapshot.get("detected_versions", {}).get(name), reason=path))
    for name in snapshot.get("unavailable_tools", []):
        if name == "langgraph_agent_server":
            details = snapshot.get("langgraph_agent_server", {})
            items.append(CapabilityItem(name=name, available=False, reason=details.get("error", "service unavailable")))
        else:
            items.append(CapabilityItem(name=name, available=False, reason="binary not found"))
    if snapshot.get("langgraph_agent_server", {}).get("available"):
        items.append(CapabilityItem(name="langgraph_agent_server", available=True, reason=snapshot.get("langgraph_agent_server", {}).get("base_url")))
    return CapabilitiesResponse(tools=sorted(items, key=lambda i: i.name))


@router.get("/profiles")
def profiles() -> dict:
    s = get_settings()
    return {
        "copilot_cheap_a": s.copilot_model_cheap_a,
        "copilot_cheap_b": s.copilot_model_cheap_b,
        "claude_review": s.claude_model_review,
        "default_profiles": ["terminal_safe", "google-readonly", "codex_iterative"],
    }


@router.get("/context", response_model=ContextResponse)
def get_context() -> ContextResponse:
    s = get_settings()
    snap = get_context_service().get_context(refresh=False)
    created_at = datetime.fromisoformat(snap["created_at"])
    age = (datetime.now(timezone.utc) - created_at).total_seconds()
    summary = ContextSummary(
        context_id=snap["context_id"],
        created_at=created_at,
        stale=age > s.context_ttl_seconds,
        ttl_seconds=s.context_ttl_seconds,
    )
    return ContextResponse(summary=summary, snapshot=ContextSnapshot(**snap))


@router.post("/context/refresh", response_model=ContextResponse)
def refresh_context() -> ContextResponse:
    s = get_settings()
    snap = get_context_service().refresh_context()
    created_at = datetime.fromisoformat(snap["created_at"])
    summary = ContextSummary(context_id=snap["context_id"], created_at=created_at, stale=False, ttl_seconds=s.context_ttl_seconds)
    return ContextResponse(summary=summary, snapshot=ContextSnapshot(**snap))


@router.get("/context/capabilities", response_model=ContextCapabilitiesResponse)
def context_capabilities() -> ContextCapabilitiesResponse:
    snap = get_context_service().get_context(refresh=False)
    caps = get_context_service().capabilities(snap)
    return ContextCapabilitiesResponse(**caps)


@router.get("/context/scripts", response_model=ScriptsResponse)
def context_scripts() -> ScriptsResponse:
    snap = get_context_service().get_context(refresh=False)
    return ScriptsResponse(items=snap.get("detected_scripts", []))


@router.get("/context/repos", response_model=ReposResponse)
def context_repos() -> ReposResponse:
    snap = get_context_service().get_context(refresh=False)
    return ReposResponse(items=snap.get("detected_repos", []))


@router.get("/path-policy", response_model=PathPolicySummary)
def get_path_policy() -> PathPolicySummary:
    return PathPolicySummary(**get_path_policy_service().summary())


@router.get("/path-policy/effective", response_model=PathPolicyEffectiveResponse)
def get_path_policy_effective(path: str) -> PathPolicyEffectiveResponse:
    policy = get_path_policy_service()
    checks = [
        policy.evaluate(path, "read"),
        policy.evaluate(path, "write"),
        policy.evaluate(path, "create_file"),
        policy.evaluate(path, "create_dir"),
        policy.evaluate(path, "delete"),
        policy.evaluate(path, "execute"),
    ]
    return PathPolicyEffectiveResponse(path=path, checks=checks)


@router.post("/path-policy/check", response_model=PathAccessCheckResponse)
def check_path_policy(payload: PathAccessCheckRequest) -> PathAccessCheckResponse:
    return get_path_policy_service().evaluate(payload.path, payload.action)


@router.get("/trash", response_model=TrashInfoResponse)
def get_trash_info(scope: str | None = None) -> TrashInfoResponse:
    return TrashInfoResponse(**get_trash_service().list(scope=scope))


@router.post("/trash/create", response_model=TrashCreateResponse)
def create_trash_space(payload: TrashCreateRequest) -> TrashCreateResponse:
    return TrashCreateResponse(**get_trash_service().create_space(task_id=payload.task_id, label=payload.label, scope=payload.scope))


@router.post("/trash/cleanup", response_model=TrashCleanupResponse)
def cleanup_trash(payload: TrashCleanupRequest) -> TrashCleanupResponse:
    return TrashCleanupResponse(**get_trash_service().cleanup(dry_run=payload.dry_run, ttl_days=payload.ttl_days, scope=payload.scope))


@router.get("/trash/{task_id}")
def get_trash_for_task(task_id: str, scope: str | None = None) -> dict:
    return get_trash_service().get_task_trash(task_id, scope=scope)


@router.post("/repo/langgraph/structure", response_model=RepoStructureResponse)
def list_langgraph_repo_structure(payload: RepoStructureRequest) -> RepoStructureResponse:
    try:
        data = get_repo_ops_service().list_repo_structure(max_depth=payload.max_depth, include_hidden=payload.include_hidden)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RepoStructureResponse(**data)


@router.post("/repo/langgraph/tests", response_model=RepoRunTestsResponse)
def run_langgraph_repo_tests(payload: RepoRunTestsRequest) -> RepoRunTestsResponse:
    try:
        data = get_repo_ops_service().run_repo_tests(pytest_args=payload.pytest_args, timeout_seconds=payload.timeout_seconds)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RepoRunTestsResponse(**data)


@router.post("/repo/langgraph/edit", response_model=RepoEditFileResponse)
def edit_langgraph_repo_file(payload: RepoEditFileRequest) -> RepoEditFileResponse:
    try:
        data = get_repo_ops_service().edit_repo_file(
            relative_path=payload.relative_path,
            content=payload.content,
            mode=payload.mode,
            create_dirs=payload.create_dirs,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RepoEditFileResponse(**data)


@router.get("/langgraph/capabilities", response_model=LanggraphCapabilitiesResponse)
def get_langgraph_capabilities() -> LanggraphCapabilitiesResponse:
    return LanggraphCapabilitiesResponse(**get_repo_ops_service().get_langgraph_capabilities())


@router.post("/delegate/complex", response_model=DelegateComplexTaskResponse)
def delegate_complex_task(payload: DelegateComplexTaskRequest) -> DelegateComplexTaskResponse:
    try:
        data = get_repo_ops_service().delegate_complex_task(
            user_goal=payload.user_goal,
            context=payload.context,
            max_iterations=payload.max_iterations,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DelegateComplexTaskResponse(**data)


@router.post("/route", response_model=RouteDecision)
def route(payload: RouteTaskRequest) -> RouteDecision:
    return get_task_service().route(payload)


@router.post("/run", response_model=TaskResponse)
def run(payload: RoutedRunRequest) -> TaskResponse:
    return get_task_service().run_routed(payload, execution_mode=payload.execution_mode)


@router.post("/run/command", response_model=TaskResponse)
def run_command(payload: RunCommandRequest) -> TaskResponse:
    try:
        return get_task_service().run_command(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run/script", response_model=TaskResponse)
def run_script(payload: RunScriptRequest) -> TaskResponse:
    try:
        return get_task_service().run_script(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run/copilot", response_model=TaskResponse)
def run_copilot(payload: ToolTaskRequest) -> TaskResponse:
    return get_task_service().run_tool_task("copilot", payload, default_profile="copilot_cheap_a")


@router.post("/run/claude-review", response_model=TaskResponse)
def run_claude(payload: ToolTaskRequest) -> TaskResponse:
    return get_task_service().run_tool_task("claude", payload, default_profile="claude_review")


@router.post("/run/codex", response_model=TaskResponse)
def run_codex(payload: ToolTaskRequest) -> TaskResponse:
    return get_task_service().run_tool_task("codex", payload, default_profile="codex_iterative")


@router.post("/run/google-cli", response_model=TaskResponse)
def run_google(payload: GoogleCliTaskRequest) -> TaskResponse:
    try:
        return get_task_service().run_google_cli(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str) -> TaskResponse:
    try:
        return get_task_service().get_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/logs", response_model=LogsResponse)
def get_task_logs(task_id: str) -> LogsResponse:
    try:
        stdout, stderr = get_task_service().get_logs(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LogsResponse(task_id=task_id, stdout=stdout, stderr=stderr)


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(limit: int = Query(default=50, ge=1, le=200)) -> TaskListResponse:
    items = get_task_service().list_tasks(limit=limit)
    return TaskListResponse(total=len(items), items=items)


@router.post("/sessions", response_model=SessionResponse)
def create_session(payload: SessionCreateRequest) -> SessionResponse:
    item = get_task_service().create_session(name=payload.name, metadata=payload.metadata)
    return SessionResponse(
        session_id=item["session_id"],
        created_at=datetime.fromisoformat(item["created_at"]),
        name=item.get("name"),
        metadata=item.get("metadata", {}),
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    try:
        item = get_task_service().get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionResponse(
        session_id=item["session_id"],
        created_at=datetime.fromisoformat(item["created_at"]),
        name=item.get("name"),
        metadata=item.get("metadata", {}),
    )

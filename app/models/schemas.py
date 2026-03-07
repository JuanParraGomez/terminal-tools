from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]
ExecutionMode = Literal["sync", "async"]
AllowedMutationLevel = Literal["readonly", "safe_write", "mutative"]
ToolName = Literal["terminal", "copilot", "claude", "codex", "gcloud", "gemini_cli", "langgraph_agent_server"]


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str


class CapabilityItem(BaseModel):
    name: str
    available: bool
    reason: str | None = None
    version: str | None = None


class CapabilitiesResponse(BaseModel):
    tools: list[CapabilityItem]
    security_mode: str = "allowlist"


class RouteTaskRequest(BaseModel):
    task_type: str | None = None
    user_goal: str = Field(..., min_length=1)
    complexity: int = Field(default=2, ge=1, le=5)
    needs_plan: bool = False
    needs_second_opinion: bool = False
    target_environment: str = "local"
    requires_iteration: bool = False
    requires_code_changes: bool = False
    allowed_mutation_level: AllowedMutationLevel = "readonly"


class RoutedRunRequest(RouteTaskRequest):
    execution_mode: ExecutionMode = "sync"


class RouteDecision(BaseModel):
    selected_tool: ToolName
    selected_profile: str
    reasoning_short: str
    execution_mode: ExecutionMode
    requires_context_sections: list[str]


class RunBaseRequest(BaseModel):
    user_goal: str = Field(..., min_length=1)
    execution_mode: ExecutionMode = "sync"
    timeout_seconds: int | None = Field(default=None, ge=1, le=1800)
    cwd: str | None = None


class RunCommandRequest(RunBaseRequest):
    command: list[str] = Field(..., min_length=1)
    dry_run: bool = False
    allow_mutative: bool = False


class RunScriptRequest(RunBaseRequest):
    script_path: str
    args: list[str] = Field(default_factory=list)
    dry_run: bool = False
    allow_mutative: bool = False


class ToolTaskRequest(RunBaseRequest):
    provider_model_alias: str | None = None
    context_hint: str | None = None


class GoogleCliTaskRequest(RunBaseRequest):
    command: list[str] | None = None
    recipe: str | None = None
    recipe_args: dict[str, str] = Field(default_factory=dict)
    dry_run: bool = False
    allow_mutative: bool = False


class SessionCreateRequest(BaseModel):
    name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    session_id: str
    created_at: datetime
    name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    selected_tool: str
    selected_profile: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: str | None = None
    error: str | None = None
    cwd: str | None = None
    command: list[str] | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    stdout_path: str | None = None
    stderr_path: str | None = None
    context_id: str | None = None
    context_freshness: str | None = None
    used_context_sections: list[str] = Field(default_factory=list)


class TaskListResponse(BaseModel):
    total: int
    items: list[TaskResponse]


class LogsResponse(BaseModel):
    task_id: str
    stdout: str
    stderr: str


class ContextSnapshot(BaseModel):
    context_id: str
    created_at: datetime
    hostname: str | None = None
    os_info: dict[str, Any]
    shell_info: dict[str, Any]
    allowed_workdirs: list[str]
    allowed_script_dirs: list[str]
    detected_binaries: dict[str, str]
    detected_versions: dict[str, str]
    detected_scripts: list[str]
    detected_repos: list[dict[str, Any]]
    google_context: dict[str, Any]
    available_tools: list[str]
    unavailable_tools: list[str]
    langgraph_agent_server: dict[str, Any] = Field(default_factory=dict)
    security_mode: str
    path_policy_summary: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ContextSummary(BaseModel):
    context_id: str
    created_at: datetime
    stale: bool
    ttl_seconds: int


class ContextResponse(BaseModel):
    summary: ContextSummary
    snapshot: ContextSnapshot


class ContextCapabilitiesResponse(BaseModel):
    available_tools: list[str]
    unavailable_tools: list[str]
    detected_binaries: dict[str, str]


class ScriptsResponse(BaseModel):
    items: list[str]


class ReposResponse(BaseModel):
    items: list[dict[str, Any]]


PathPermission = Literal["read_only", "read_write", "create_only", "scratch", "blocked"]
PathAction = Literal["read", "write", "create_file", "create_dir", "delete", "execute"]


class PathRule(BaseModel):
    workspace: str | None = None
    path: str
    permission: PathPermission
    allow_delete: bool = False
    allow_execute: bool = False
    allow_create_files: bool = False
    allow_create_dirs: bool = False
    ttl_days: int | None = None
    notes: str | None = None
    is_pattern: bool = False


class PathPolicySummary(BaseModel):
    unknown_paths: str
    follow_symlinks: bool
    workspaces: list[dict[str, Any]]
    protected: list[PathRule]


class PathAccessCheckRequest(BaseModel):
    path: str
    action: PathAction


class PathAccessCheckResponse(BaseModel):
    path: str
    action: PathAction
    resolved_permission: PathPermission
    allowed: bool
    matched_rule: PathRule | None = None
    reason: str


class PathPolicyEffectiveResponse(BaseModel):
    path: str
    checks: list[PathAccessCheckResponse]


class TrashInfoResponse(BaseModel):
    trash_root: str
    ttl_days: int
    total_items: int
    items: list[dict[str, Any]]
    scope: str = "default"


class TrashCreateRequest(BaseModel):
    task_id: str
    label: str | None = None
    scope: str | None = None


class TrashCreateResponse(BaseModel):
    task_id: str
    trash_path: str
    meta_path: str
    created: bool
    scope: str = "default"


class TrashCleanupRequest(BaseModel):
    dry_run: bool = False
    ttl_days: int | None = None
    scope: str | None = None


class TrashCleanupResponse(BaseModel):
    dry_run: bool
    ttl_days: int
    deleted_items: list[str]
    kept_items: list[str]
    scope: str = "default"


class RepoStructureRequest(BaseModel):
    max_depth: int = Field(default=3, ge=1, le=8)
    include_hidden: bool = False


class RepoStructureResponse(BaseModel):
    repo_root: str
    max_depth: int
    items: list[dict[str, Any]]


class RepoRunTestsRequest(BaseModel):
    pytest_args: list[str] = Field(default_factory=lambda: ["-q"])
    timeout_seconds: int | None = Field(default=300, ge=1, le=1800)


class RepoRunTestsResponse(BaseModel):
    ok: bool
    command: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str


class RepoEditFileRequest(BaseModel):
    relative_path: str = Field(min_length=1)
    content: str
    mode: Literal["create", "overwrite", "append"] = "overwrite"
    create_dirs: bool = True


class RepoEditFileResponse(BaseModel):
    ok: bool
    path: str
    mode: str
    bytes_written: int


class DisposableArtifactRequest(BaseModel):
    user_goal: str = Field(min_length=3)
    file_name: str = Field(min_length=3)
    content: str = Field(min_length=1)
    content_type: str = "code"
    scope: str | None = "langgraph_agent_server"


class DisposableArtifactResponse(BaseModel):
    ok: bool
    classified_as_disposable: bool
    reason: str
    task_id: str
    trash_path: str
    file_path: str
    content_type: str
    bytes_written: int


class DelegateComplexTaskRequest(BaseModel):
    user_goal: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    max_iterations: int = Field(default=3, ge=1, le=10)


class DelegateComplexTaskResponse(BaseModel):
    ok: bool
    delegated: bool
    provider: str
    data: dict[str, Any] = Field(default_factory=dict)


class LanggraphCapabilitiesResponse(BaseModel):
    enabled: bool
    available: bool
    base_url: str
    mcp_url: str
    details: dict[str, Any] = Field(default_factory=dict)

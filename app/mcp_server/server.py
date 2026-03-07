from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from app.models.schemas import GoogleCliTaskRequest, RouteTaskRequest, RunCommandRequest, RunScriptRequest, ToolTaskRequest
from app.services.container import (
    get_context_service,
    get_path_policy_service,
    get_repo_ops_service,
    get_task_service,
    get_trash_service,
)

mcp = FastMCP("terminal-tools-mcp")


@mcp.tool()
def terminal_health() -> dict[str, Any]:
    return {"status": "ok", "service": "terminal-tools"}


@mcp.tool()
def terminal_list_capabilities() -> dict[str, Any]:
    snap = get_context_service().get_context(refresh=False)
    return get_context_service().capabilities(snap)


@mcp.tool()
def terminal_get_context() -> dict[str, Any]:
    return get_context_service().get_context(refresh=False)


@mcp.tool()
def terminal_refresh_context() -> dict[str, Any]:
    return get_context_service().refresh_context()


@mcp.tool()
def terminal_get_capabilities() -> dict[str, Any]:
    snap = get_context_service().get_context(refresh=False)
    return get_context_service().capabilities(snap)


@mcp.tool()
def terminal_get_scripts() -> dict[str, Any]:
    snap = get_context_service().get_context(refresh=False)
    return {"items": snap.get("detected_scripts", [])}


@mcp.tool()
def terminal_get_repos() -> dict[str, Any]:
    snap = get_context_service().get_context(refresh=False)
    return {"items": snap.get("detected_repos", [])}


@mcp.tool()
def terminal_get_path_policy() -> dict[str, Any]:
    return get_path_policy_service().summary()


@mcp.tool()
def terminal_check_path_access(path: str, action: str) -> dict[str, Any]:
    return get_path_policy_service().evaluate(path, action).model_dump()


@mcp.tool()
def terminal_get_trash_info(scope: str | None = None) -> dict[str, Any]:
    return get_trash_service().list(scope=scope)


@mcp.tool()
def terminal_create_trash_space(task_id: str, label: str | None = None, scope: str | None = None) -> dict[str, Any]:
    return get_trash_service().create_space(task_id=task_id, label=label, scope=scope)


@mcp.tool()
def terminal_cleanup_trash(dry_run: bool = False, ttl_days: int | None = None, scope: str | None = None) -> dict[str, Any]:
    return get_trash_service().cleanup(dry_run=dry_run, ttl_days=ttl_days, scope=scope)


@mcp.tool()
def terminal_list_repo_structure(max_depth: int = 3, include_hidden: bool = False) -> dict[str, Any]:
    return get_repo_ops_service().list_repo_structure(max_depth=max_depth, include_hidden=include_hidden)


@mcp.tool()
def terminal_run_repo_tests(pytest_args: list[str] | None = None, timeout_seconds: int | None = 300) -> dict[str, Any]:
    return get_repo_ops_service().run_repo_tests(pytest_args=pytest_args, timeout_seconds=timeout_seconds)


@mcp.tool()
def terminal_edit_repo_file(relative_path: str, content: str, mode: str = "overwrite", create_dirs: bool = True) -> dict[str, Any]:
    return get_repo_ops_service().edit_repo_file(
        relative_path=relative_path,
        content=content,
        mode=mode,
        create_dirs=create_dirs,
    )


@mcp.tool()
def terminal_delegate_complex_task(user_goal: str, context: dict[str, Any] | None = None, max_iterations: int = 3) -> dict[str, Any]:
    return get_repo_ops_service().delegate_complex_task(
        user_goal=user_goal,
        context=context or {},
        max_iterations=max_iterations,
    )


@mcp.tool()
def terminal_get_langgraph_capabilities() -> dict[str, Any]:
    return get_repo_ops_service().get_langgraph_capabilities()


@mcp.tool()
def terminal_route_task(
    user_goal: str,
    task_type: str | None = None,
    complexity: int = 2,
    needs_plan: bool = False,
    needs_second_opinion: bool = False,
    target_environment: str = "local",
    requires_iteration: bool = False,
    requires_code_changes: bool = False,
    allowed_mutation_level: str = "readonly",
) -> dict[str, Any]:
    req = RouteTaskRequest(
        task_type=task_type,
        user_goal=user_goal,
        complexity=complexity,
        needs_plan=needs_plan,
        needs_second_opinion=needs_second_opinion,
        target_environment=target_environment,
        requires_iteration=requires_iteration,
        requires_code_changes=requires_code_changes,
        allowed_mutation_level=allowed_mutation_level,
    )
    return get_task_service().route(req).model_dump()


@mcp.tool()
def terminal_run_command(
    user_goal: str,
    command: list[str],
    execution_mode: str = "sync",
    timeout_seconds: int | None = None,
    cwd: str | None = None,
    allow_mutative: bool = False,
) -> dict[str, Any]:
    req = RunCommandRequest(
        user_goal=user_goal,
        command=command,
        execution_mode=execution_mode,
        timeout_seconds=timeout_seconds,
        cwd=cwd,
        allow_mutative=allow_mutative,
    )
    return get_task_service().run_command(req).model_dump(mode="json")


@mcp.tool()
def terminal_run_script(
    user_goal: str,
    script_path: str,
    args: list[str] | None = None,
    execution_mode: str = "sync",
    timeout_seconds: int | None = None,
    cwd: str | None = None,
    allow_mutative: bool = False,
) -> dict[str, Any]:
    req = RunScriptRequest(
        user_goal=user_goal,
        script_path=script_path,
        args=args or [],
        execution_mode=execution_mode,
        timeout_seconds=timeout_seconds,
        cwd=cwd,
        allow_mutative=allow_mutative,
    )
    return get_task_service().run_script(req).model_dump(mode="json")


@mcp.tool()
def terminal_copilot_code_task(user_goal: str, execution_mode: str = "sync", cwd: str | None = None) -> dict[str, Any]:
    req = ToolTaskRequest(user_goal=user_goal, execution_mode=execution_mode, cwd=cwd)
    return get_task_service().run_tool_task("copilot", req, default_profile="copilot_cheap_a").model_dump(mode="json")


@mcp.tool()
def terminal_copilot_plan_task(
    user_goal: str,
    execution_mode: str = "sync",
    cwd: str | None = None,
    provider_model_alias: str | None = None,
) -> dict[str, Any]:
    req = ToolTaskRequest(
        user_goal=user_goal,
        execution_mode=execution_mode,
        cwd=cwd,
        provider_model_alias=provider_model_alias,
    )
    return get_task_service().run_tool_task("copilot", req, default_profile="copilot_plan").model_dump(mode="json")


@mcp.tool()
def terminal_claude_review_task(user_goal: str, execution_mode: str = "sync", cwd: str | None = None) -> dict[str, Any]:
    req = ToolTaskRequest(user_goal=user_goal, execution_mode=execution_mode, cwd=cwd)
    return get_task_service().run_tool_task("claude", req, default_profile="claude_review").model_dump(mode="json")


@mcp.tool()
def terminal_codex_iterate_task(user_goal: str, execution_mode: str = "async", cwd: str | None = None) -> dict[str, Any]:
    req = ToolTaskRequest(user_goal=user_goal, execution_mode=execution_mode, cwd=cwd)
    return get_task_service().run_tool_task("codex", req, default_profile="codex_iterative").model_dump(mode="json")


@mcp.tool()
def terminal_google_cli_task(
    user_goal: str,
    command: list[str] | None = None,
    recipe: str | None = None,
    recipe_args: dict[str, str] | None = None,
    execution_mode: str = "sync",
    timeout_seconds: int | None = None,
    cwd: str | None = None,
    allow_mutative: bool = False,
) -> dict[str, Any]:
    req = GoogleCliTaskRequest(
        user_goal=user_goal,
        command=command,
        recipe=recipe,
        recipe_args=recipe_args or {},
        execution_mode=execution_mode,
        timeout_seconds=timeout_seconds,
        cwd=cwd,
        allow_mutative=allow_mutative,
    )
    return get_task_service().run_google_cli(req).model_dump(mode="json")


@mcp.tool()
def terminal_get_task(task_id: str) -> dict[str, Any]:
    return get_task_service().get_task(task_id).model_dump(mode="json")


@mcp.tool()
def terminal_get_logs(task_id: str) -> dict[str, Any]:
    stdout, stderr = get_task_service().get_logs(task_id)
    return {"task_id": task_id, "stdout": stdout, "stderr": stderr}


if __name__ == "__main__":
    from app.core.settings import get_settings

    settings = get_settings()
    mcp.run(transport=settings.mcp_transport, host=settings.mcp_host, port=settings.mcp_port)

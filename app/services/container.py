from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.adapters.langgraph_agent_server_adapter import LanggraphAgentServerAdapter
from app.adapters.router import AdapterRegistry
from app.core.settings import Settings, get_settings
from app.routing.router import RoutingService
from app.security.path_policy_service import PathPolicyService
from app.security.validator import SecurityValidator
from app.services.context_service import ContextService
from app.services.executor import CommandExecutor
from app.services.langgraph_service import LanggraphService
from app.services.recipe_service import RecipeService
from app.services.repo_ops_service import RepoOpsService
from app.services.task_service import TaskService
from app.services.trash_service import TrashService
from app.storage.db import Database


@lru_cache(maxsize=1)
def get_db() -> Database:
    settings = get_settings()
    return Database(settings.db_path)


@lru_cache(maxsize=1)
def get_path_policy_service() -> PathPolicyService:
    app_dir = Path(__file__).resolve().parents[1]
    return PathPolicyService(app_dir / "security" / "path_policy.yaml")


@lru_cache(maxsize=1)
def get_trash_service() -> TrashService:
    settings = get_settings()
    return TrashService(settings=settings)


@lru_cache(maxsize=1)
def get_executor() -> CommandExecutor:
    settings = get_settings()
    return CommandExecutor(settings.default_timeout_seconds, settings.max_output_chars)


@lru_cache(maxsize=1)
def get_langgraph_client() -> LanggraphAgentServerAdapter:
    settings = get_settings()
    return LanggraphAgentServerAdapter(
        base_url=settings.langgraph_agent_server_base_url,
        mcp_url=settings.langgraph_agent_server_mcp_url,
        timeout_seconds=10,
    )


@lru_cache(maxsize=1)
def get_langgraph_service() -> LanggraphService:
    return LanggraphService(settings=get_settings(), client=get_langgraph_client())


@lru_cache(maxsize=1)
def get_context_service() -> ContextService:
    settings = get_settings()
    return ContextService(
        settings=settings,
        db=get_db(),
        app_dir=Path(__file__).resolve().parents[1],
        path_policy=get_path_policy_service(),
    )


@lru_cache(maxsize=1)
def get_validator() -> SecurityValidator:
    settings: Settings = get_settings()
    app_dir = Path(__file__).resolve().parents[1]
    return SecurityValidator(
        app_dir,
        settings.allowed_workdirs_list,
        settings.allowed_script_dirs_list,
        path_policy=get_path_policy_service(),
    )


@lru_cache(maxsize=1)
def get_repo_ops_service() -> RepoOpsService:
    return RepoOpsService(
        settings=get_settings(),
        validator=get_validator(),
        path_policy=get_path_policy_service(),
        executor=get_executor(),
        langgraph_service=get_langgraph_service(),
        trash_service=get_trash_service(),
    )


@lru_cache(maxsize=1)
def get_task_service() -> TaskService:
    settings: Settings = get_settings()
    app_dir = Path(__file__).resolve().parents[1]
    executor = get_executor()
    validator = get_validator()
    routing = RoutingService(app_dir)
    recipes = RecipeService(app_dir / "recipes")
    adapters = AdapterRegistry(settings, executor, get_langgraph_service())
    return TaskService(
        settings=settings,
        db=get_db(),
        context_service=get_context_service(),
        routing_service=routing,
        validator=validator,
        adapters=adapters,
        recipes=recipes,
        path_policy=get_path_policy_service(),
        trash_service=get_trash_service(),
    )

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.models.schemas import RouteDecision, RouteTaskRequest


class RoutingService:
    def __init__(self, base_dir: Path) -> None:
        self._policy = yaml.safe_load((base_dir / "routing" / "policy.yaml").read_text(encoding="utf-8"))
        self._patterns = yaml.safe_load((base_dir / "routing" / "task_patterns.yaml").read_text(encoding="utf-8"))

    def decide(self, request: RouteTaskRequest, available_tools: set[str]) -> RouteDecision:
        goal = request.user_goal.lower()

        if request.target_environment.lower() == "google":
            return self._select_google(goal, available_tools)

        is_complex = (
            request.complexity >= 4
            or request.requires_iteration
            or self._contains(goal, "langgraph_keywords")
            or any(k in goal for k in ["investig", "multi", "orquest", "subagente", "sintetiza"])
        )
        if is_complex and "langgraph_agent_server" in available_tools:
            return self._mk(
                "langgraph_agent_server",
                "langgraph_complex",
                "Complex multi-step task delegated to langgraph-agent-server",
                ["repos", "scripts", "constraints", "security", "workdirs"],
            )

        if request.needs_plan or request.needs_second_opinion or self._contains(goal, "claude_keywords"):
            if "claude" in available_tools:
                return self._mk("claude", "claude_review", "Needs planning/review", ["repos", "git_status", "constraints"])

        if request.requires_iteration or (request.requires_code_changes and request.complexity >= 4) or self._contains(goal, "codex_keywords"):
            if "codex" in available_tools:
                return self._mk("codex", "codex_iterative", "Complex iterative code task", ["repos", "git_status", "workdirs", "commands"])

        if (request.requires_code_changes and request.complexity <= 3) or self._contains(goal, "copilot_keywords"):
            if "copilot" in available_tools:
                return self._mk("copilot", "copilot_cheap_a", "Focused coding task", ["repos", "files", "commands"])

        if self._contains(goal, "google_keywords"):
            return self._select_google(goal, available_tools)

        return self._mk("terminal", "terminal_safe", "Default local operational task", ["security", "workdirs", "scripts"])

    def _select_google(self, goal: str, available_tools: set[str]) -> RouteDecision:
        if "gcloud" in available_tools:
            return self._mk("gcloud", "google-readonly", "Google environment task", ["google_context", "recipes", "commands"])
        if "gemini_cli" in available_tools:
            return self._mk("gemini_cli", "google-assist", "Google environment task via gemini cli", ["google_context", "recipes", "commands"])
        return self._mk("terminal", "terminal_safe", "Google tool unavailable; fallback terminal", ["security", "workdirs", "scripts"])

    def _mk(self, tool: str, profile: str, reason: str, sections: list[str]) -> RouteDecision:
        mode = self._policy.get("profiles", {}).get(tool, {}).get("execution_mode", "sync")
        return RouteDecision(
            selected_tool=tool,  # type: ignore[arg-type]
            selected_profile=profile,
            reasoning_short=reason,
            execution_mode=mode,  # type: ignore[arg-type]
            requires_context_sections=sections,
        )

    def _contains(self, goal: str, key: str) -> bool:
        words = self._patterns.get(key, [])
        return any(word in goal for word in words)


def route_task(
    task_type: str | None,
    user_goal: str,
    complexity: int,
    needs_plan: bool,
    needs_second_opinion: bool,
    target_environment: str,
    requires_iteration: bool,
    requires_code_changes: bool,
    allowed_mutation_level: str,
    routing_service: RoutingService,
    available_tools: set[str],
) -> RouteDecision:
    req = RouteTaskRequest(
        task_type=task_type,
        user_goal=user_goal,
        complexity=complexity,
        needs_plan=needs_plan,
        needs_second_opinion=needs_second_opinion,
        target_environment=target_environment,
        requires_iteration=requires_iteration,
        requires_code_changes=requires_code_changes,
        allowed_mutation_level=allowed_mutation_level,  # type: ignore[arg-type]
    )
    return routing_service.decide(req, available_tools)

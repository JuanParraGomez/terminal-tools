from __future__ import annotations

from typing import Any

from app.adapters.langgraph_agent_server_adapter import LanggraphAgentServerAdapter
from app.core.settings import Settings


class LanggraphService:
    def __init__(self, settings: Settings, client: LanggraphAgentServerAdapter) -> None:
        self.settings = settings
        self.client = client

    def status(self) -> dict[str, Any]:
        if not self.settings.enable_langgraph_agent_server:
            return {
                "enabled": False,
                "available": False,
                "base_url": self.settings.langgraph_agent_server_base_url,
                "mcp_url": self.settings.langgraph_agent_server_mcp_url,
                "details": {"reason": "disabled by env"},
            }
        health = self.client.health()
        return {
            "enabled": True,
            "available": bool(health.get("available")),
            "base_url": self.settings.langgraph_agent_server_base_url,
            "mcp_url": self.settings.langgraph_agent_server_mcp_url,
            "details": health,
        }

    def capabilities(self) -> dict[str, Any]:
        status = self.status()
        if not status["enabled"]:
            return status
        caps = self.client.capabilities()
        return {
            "enabled": True,
            "available": bool(caps.get("available")),
            "base_url": self.settings.langgraph_agent_server_base_url,
            "mcp_url": self.settings.langgraph_agent_server_mcp_url,
            "details": caps,
        }

    def delegate_complex_task(self, user_goal: str, context: dict[str, Any], max_iterations: int) -> dict[str, Any]:
        if not self.settings.enable_langgraph_agent_server:
            return {
                "ok": False,
                "delegated": False,
                "provider": "langgraph_agent_server",
                "data": {"error": "langgraph_agent_server_disabled"},
            }
        health = self.client.health()
        if not health.get("available"):
            return {
                "ok": False,
                "delegated": False,
                "provider": "langgraph_agent_server",
                "data": {"error": "langgraph_agent_server_unavailable", "details": health},
            }
        try:
            payload = self.client.run_complex_task(user_goal=user_goal, context=context, max_iterations=max_iterations)
            return {
                "ok": True,
                "delegated": True,
                "provider": "langgraph_agent_server",
                "data": payload,
            }
        except Exception as exc:
            return {
                "ok": False,
                "delegated": False,
                "provider": "langgraph_agent_server",
                "data": {"error": str(exc)},
            }

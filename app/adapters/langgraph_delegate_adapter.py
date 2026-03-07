from __future__ import annotations

from app.adapters.base import AdapterRequest, AdapterResponse, BaseAdapter
from app.services.langgraph_service import LanggraphService


class LanggraphDelegateAdapter(BaseAdapter):
    name = "langgraph_agent_server"

    def __init__(self, langgraph_service: LanggraphService) -> None:
        self.langgraph_service = langgraph_service

    def execute(self, req: AdapterRequest) -> AdapterResponse:
        context = {
            "source": "terminal-tools",
            "rendered_context": req.rendered_context,
            "cwd": req.cwd,
        }
        delegated = self.langgraph_service.delegate_complex_task(
            user_goal=req.objective,
            context=context,
            max_iterations=3,
        )
        ok = bool(delegated.get("ok"))
        return AdapterResponse(
            ok=ok,
            summary="Delegated to langgraph-agent-server" if ok else "Langgraph delegation failed",
            result=delegated,
            used_context_sections=list(req.rendered_context.get("sections", {}).keys()),
        )

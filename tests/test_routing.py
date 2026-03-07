from pathlib import Path

from app.models.schemas import RouteTaskRequest
from app.routing.router import RoutingService


def test_google_target_routes_to_google_tool() -> None:
    service = RoutingService(Path(__file__).resolve().parents[1] / "app")
    req = RouteTaskRequest(user_goal="lista proyectos", target_environment="google")
    decision = service.decide(req, {"terminal", "gcloud"})
    assert decision.selected_tool == "gcloud"


def test_plan_prefers_claude() -> None:
    service = RoutingService(Path(__file__).resolve().parents[1] / "app")
    req = RouteTaskRequest(user_goal="haz plan", needs_plan=True)
    decision = service.decide(req, {"terminal", "claude"})
    assert decision.selected_tool == "claude"

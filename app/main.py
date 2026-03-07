from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.core.settings import get_settings
from app.services.container import get_context_service, get_trash_service

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    get_context_service().get_context(refresh=False)
    get_trash_service().cleanup(dry_run=False)
    get_trash_service().cleanup(dry_run=False, scope="langgraph_agent_server")

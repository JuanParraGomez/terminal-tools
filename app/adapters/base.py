from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AdapterRequest:
    objective: str
    command: list[str] | None
    cwd: str | None
    timeout_seconds: int | None
    rendered_context: dict[str, Any]
    selected_profile: str | None = None
    provider_model_alias: str | None = None
    recipe: dict[str, Any] | None = None
    env: dict[str, str] | None = None


@dataclass
class AdapterResponse:
    ok: bool
    summary: str
    result: dict[str, Any]
    used_context_sections: list[str]


class BaseAdapter:
    name: str = "base"

    def execute(self, req: AdapterRequest) -> AdapterResponse:
        raise NotImplementedError

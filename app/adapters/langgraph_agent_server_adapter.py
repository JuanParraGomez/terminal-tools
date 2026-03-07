from __future__ import annotations

from typing import Any

import httpx


class LanggraphAgentServerAdapter:
    def __init__(self, base_url: str, mcp_url: str, timeout_seconds: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.mcp_url = mcp_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def health(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.get(f"{self.base_url}/health")
                resp.raise_for_status()
                return {"available": True, "base_url": self.base_url, "mcp_url": self.mcp_url, "data": resp.json()}
        except Exception as exc:
            return {"available": False, "base_url": self.base_url, "mcp_url": self.mcp_url, "error": str(exc)}

    def capabilities(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.get(f"{self.base_url}/capabilities")
                resp.raise_for_status()
                return {"available": True, "data": resp.json()}
        except Exception as exc:
            return {"available": False, "error": str(exc)}

    def run_complex_task(self, user_goal: str, context: dict[str, Any], max_iterations: int = 3) -> dict[str, Any]:
        payload = {
            "goal": user_goal,
            "context": context,
            "max_iterations": max_iterations,
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(f"{self.base_url}/run/complex", json=payload)
            resp.raise_for_status()
            return resp.json()

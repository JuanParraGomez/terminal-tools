from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.settings import Settings
from app.core.utils import safe_env_metadata
from app.security.path_policy_service import PathPolicyService
from app.storage.db import Database


class ContextService:
    def __init__(self, settings: Settings, db: Database, app_dir: Path, path_policy: PathPolicyService) -> None:
        self.settings = settings
        self.db = db
        self.app_dir = app_dir
        self.path_policy = path_policy

    def get_context(self, refresh: bool = False) -> dict:
        latest = self.db.get_latest_context_snapshot()
        if refresh or not latest:
            return self.refresh_context()

        created_at = datetime.fromisoformat(latest["created_at"])
        age = (datetime.now(timezone.utc) - created_at).total_seconds()
        if age > self.settings.context_ttl_seconds and self.settings.auto_refresh_context_on_stale:
            return self.refresh_context()
        return latest

    def refresh_context(self) -> dict:
        created_at = datetime.now(timezone.utc).isoformat()
        context_id = f"ctx_{uuid4().hex[:12]}"
        binaries = {
            "copilot": self.settings.copilot_bin,
            "codex": self.settings.codex_bin,
            "claude": self.settings.claude_bin,
            "gcloud": self.settings.gcloud_bin,
            "gemini_cli": self.settings.gemini_cli_bin,
            "git": "git",
            "python": "python3",
            "node": "node",
            "bash": "bash",
        }

        detected_binaries: dict[str, str] = {}
        detected_versions: dict[str, str] = {}
        available_tools: list[str] = []
        unavailable_tools: list[str] = []

        for tool, cmd in binaries.items():
            path = shutil.which(cmd)
            if path:
                detected_binaries[tool] = path
                version = self._detect_version(cmd)
                if version:
                    detected_versions[tool] = version
                if tool in {"copilot", "codex", "claude", "gcloud", "gemini_cli", "terminal"}:
                    available_tools.append(tool)
            else:
                if tool in {"copilot", "codex", "claude", "gcloud", "gemini_cli"}:
                    unavailable_tools.append(tool)

        scripts = self._detect_scripts()
        repos = self._detect_repos()
        google_context = self._detect_google_context(detected_binaries)

        snapshot = {
            "context_id": context_id,
            "created_at": created_at,
            "hostname": socket.gethostname(),
            "os_info": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
            },
            "shell_info": {
                "shell": os.environ.get("SHELL", "unknown"),
            },
            "allowed_workdirs": [str(p) for p in self.settings.allowed_workdirs_list],
            "allowed_script_dirs": [str(p) for p in self.settings.allowed_script_dirs_list],
            "detected_binaries": detected_binaries,
            "detected_versions": detected_versions,
            "detected_scripts": scripts,
            "detected_repos": repos,
            "google_context": google_context,
            "available_tools": sorted(set(available_tools + ["terminal"])),
            "unavailable_tools": sorted(set(unavailable_tools)),
            "security_mode": "allowlist",
            "path_policy_summary": self.path_policy.render_summary_for_context(),
            "notes": ["No sensitive env values stored", f"env_keys={len(safe_env_metadata())}"],
        }

        self.db.save_context_snapshot(context_id, snapshot)
        (self.settings.context_dir / "current_context.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        return snapshot

    def render_for_tool(self, snapshot: dict, selected_tool: str, sections: list[str], objective: str) -> dict:
        rendered = {
            "objective": objective,
            "selected_tool": selected_tool,
            "context_id": snapshot["context_id"],
            "sections": {},
        }
        for section in sections:
            if section == "repos":
                rendered["sections"][section] = snapshot.get("detected_repos", [])
            elif section == "scripts":
                rendered["sections"][section] = snapshot.get("detected_scripts", [])
            elif section == "google_context":
                rendered["sections"][section] = snapshot.get("google_context", {})
            elif section == "workdirs":
                rendered["sections"][section] = snapshot.get("allowed_workdirs", [])
            elif section == "commands":
                rendered["sections"][section] = list(snapshot.get("detected_binaries", {}).keys())
            elif section == "security":
                rendered["sections"][section] = {
                    "security_mode": snapshot.get("security_mode", "allowlist"),
                    "path_policy_summary": self.path_policy.render_summary_for_context(task_id=objective[:24].replace(" ", "_")),
                }
            elif section == "git_status":
                rendered["sections"][section] = [{"path": r.get("path"), "branch": r.get("branch"), "dirty": r.get("dirty")} for r in snapshot.get("detected_repos", [])]
            elif section == "constraints":
                rendered["sections"][section] = {
                    "mutative_requires_confirmation": True,
                    "allowed_workdirs": snapshot.get("allowed_workdirs", []),
                    "path_policy_summary": self.path_policy.render_summary_for_context(),
                    "write_constraints": {
                        "allow_delete": False,
                        "prefer_scratch_for_temporary_outputs": True,
                    },
                }
        return rendered

    def capabilities(self, snapshot: dict) -> dict:
        return {
            "available_tools": snapshot.get("available_tools", []),
            "unavailable_tools": snapshot.get("unavailable_tools", []),
            "detected_binaries": snapshot.get("detected_binaries", {}),
        }

    def _detect_version(self, cmd: str) -> str | None:
        for args in ([cmd, "--version"], [cmd, "version"]):
            try:
                proc = subprocess.run(args, capture_output=True, text=True, timeout=2, check=False)
                line = (proc.stdout or proc.stderr).strip().splitlines()
                if line:
                    return line[0][:160]
            except Exception:
                continue
        return None

    def _detect_scripts(self) -> list[str]:
        scripts: list[str] = []
        for directory in self.settings.allowed_script_dirs_list:
            if not directory.exists():
                continue
            for item in directory.glob("*.sh"):
                scripts.append(str(item.resolve()))
        return sorted(set(scripts))

    def _detect_repos(self) -> list[dict]:
        repos: list[dict] = []
        git_bin = shutil.which("git")
        if not git_bin:
            return repos

        for root in self.settings.allowed_workdirs_list:
            if not root.exists() or not root.is_dir():
                continue
            children: list[Path] = [root]
            try:
                children.extend([p for p in root.iterdir() if p.is_dir()])
            except PermissionError:
                continue
            for path in children:
                try:
                    if not (path / ".git").exists():
                        continue
                    branch = self._git_cmd(path, [git_bin, "rev-parse", "--abbrev-ref", "HEAD"])
                    status = self._git_cmd(path, [git_bin, "status", "--porcelain"])
                    repos.append({
                        "path": str(path.resolve()),
                        "branch": branch.strip() or "unknown",
                        "dirty": bool(status.strip()),
                    })
                except PermissionError:
                    continue
        return repos

    def _detect_google_context(self, binaries: dict[str, str]) -> dict:
        gcloud = binaries.get("gcloud")
        if not gcloud:
            return {"installed": False, "auth_ok": False, "active_account": None, "active_project": None}

        active_account = self._gcloud_value([gcloud, "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
        active_project = self._gcloud_value([gcloud, "config", "get-value", "project", "--quiet"])
        return {
            "installed": True,
            "auth_ok": bool(active_account),
            "active_account": active_account or None,
            "active_project": active_project or None,
        }

    def _gcloud_value(self, cmd: list[str]) -> str:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=4, check=False)
            return (proc.stdout or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _git_cmd(cwd: Path, cmd: list[str]) -> str:
        try:
            proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=3, check=False)
            return (proc.stdout or "").strip()
        except Exception:
            return ""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.settings import Settings


class TrashService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.trash_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings.langgraph_agent_repo_trash_dir.mkdir(parents=True, exist_ok=True)

    def list(self, scope: str | None = None) -> dict:
        root = self._resolve_root(scope)
        items = []
        for p in sorted(root.glob("task_*")):
            meta = self._load_meta(p)
            items.append(
                {
                    "task_id": p.name,
                    "path": str(p),
                    "created_at": meta.get("created_at"),
                    "label": meta.get("label"),
                    "exists": p.exists(),
                }
            )
        return {
            "trash_root": str(root),
            "ttl_days": self.settings.trash_ttl_days,
            "total_items": len(items),
            "items": items,
            "scope": scope or "default",
        }

    def create_space(self, task_id: str, label: str | None = None, scope: str | None = None) -> dict:
        root = self._resolve_root(scope)
        safe_task = f"task_{task_id.replace('/', '_').replace('..', '_')}"
        p = root / safe_task
        p.mkdir(parents=True, exist_ok=True)
        meta = {
            "task_id": task_id,
            "label": label,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = p / ".meta.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return {
            "task_id": task_id,
            "trash_path": str(p),
            "meta_path": str(meta_path),
            "created": True,
            "scope": scope or "default",
        }

    def get_task_trash(self, task_id: str, scope: str | None = None) -> dict:
        root = self._resolve_root(scope)
        safe_task = f"task_{task_id.replace('/', '_').replace('..', '_')}"
        p = root / safe_task
        if not p.exists():
            return {"task_id": task_id, "exists": False, "trash_path": str(p), "items": []}
        files = [str(x) for x in p.rglob("*") if x.is_file() and x.name != ".meta.json"]
        return {"task_id": task_id, "exists": True, "trash_path": str(p), "items": files, "scope": scope or "default"}

    def cleanup(self, dry_run: bool = False, ttl_days: int | None = None, scope: str | None = None) -> dict:
        root = self._resolve_root(scope)
        ttl = ttl_days or self.settings.trash_ttl_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl)
        deleted: list[str] = []
        kept: list[str] = []

        for p in sorted(root.glob("task_*")):
            created = self._created_at(p)
            if created is None or created >= cutoff:
                kept.append(str(p))
                continue
            if dry_run:
                deleted.append(str(p))
                continue
            # Safety guard: never delete outside root
            try:
                p.resolve().relative_to(root.resolve())
            except ValueError:
                kept.append(str(p))
                continue
            shutil.rmtree(p, ignore_errors=True)
            deleted.append(str(p))

        return {
            "dry_run": dry_run,
            "ttl_days": ttl,
            "deleted_items": deleted,
            "kept_items": kept,
            "scope": scope or "default",
        }

    def _resolve_root(self, scope: str | None) -> Path:
        if scope == "langgraph_agent_server":
            root = self.settings.langgraph_agent_repo_trash_dir
        else:
            root = self.root
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _created_at(self, task_path: Path) -> datetime | None:
        meta = self._load_meta(task_path)
        value = meta.get("created_at")
        if value:
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return None
        try:
            return datetime.fromtimestamp(task_path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _load_meta(task_path: Path) -> dict:
        meta_path = task_path / ".meta.json"
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

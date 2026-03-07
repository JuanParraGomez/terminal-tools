import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.settings import Settings
from app.services.trash_service import TrashService


def test_trash_cleanup_by_ttl(tmp_path: Path) -> None:
    trash_dir = tmp_path / "trash"
    settings = Settings(trash_dir=trash_dir, trash_ttl_days=7)
    svc = TrashService(settings)

    old = svc.create_space("old-task")
    old_meta = Path(old["meta_path"])
    meta = json.loads(old_meta.read_text(encoding="utf-8"))
    meta["created_at"] = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()
    old_meta.write_text(json.dumps(meta), encoding="utf-8")

    svc.create_space("new-task")
    result = svc.cleanup(dry_run=False, ttl_days=7)
    assert any("old-task" in item for item in result["deleted_items"])


def test_trash_cleanup_dry_run(tmp_path: Path) -> None:
    trash_dir = tmp_path / "trash"
    settings = Settings(trash_dir=trash_dir, trash_ttl_days=7)
    svc = TrashService(settings)
    svc.create_space("task-a")
    result = svc.cleanup(dry_run=True, ttl_days=0)
    assert result["dry_run"] is True

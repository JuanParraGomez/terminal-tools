from pathlib import Path

from app.security.path_policy_service import PathPolicyService


def _policy_file(tmp_path: Path) -> Path:
    p = tmp_path / "path_policy.yaml"
    p.write_text(
        """
defaults:
  unknown_paths: blocked
  follow_symlinks: false
workspaces:
  - name: ws
    root: /tmp/ws
    rules:
      - path: /tmp/ws/exact.txt
        permission: read_only
      - path: /tmp/ws/scratch
        permission: scratch
        allow_create_files: true
        allow_create_dirs: true
        allow_delete: true
      - path: /tmp/ws/**/generated/*.tmp
        permission: create_only
        is_pattern: true
protected:
  - path: /tmp/ws/**/.env
    permission: blocked
    is_pattern: true
""",
        encoding="utf-8",
    )
    return p


def test_exact_over_pattern_and_read_only(tmp_path: Path) -> None:
    svc = PathPolicyService(_policy_file(tmp_path))
    check = svc.evaluate("/tmp/ws/exact.txt", "read")
    assert check.allowed is True
    check_write = svc.evaluate("/tmp/ws/exact.txt", "write")
    assert check_write.allowed is False


def test_unknown_path_blocked(tmp_path: Path) -> None:
    svc = PathPolicyService(_policy_file(tmp_path))
    check = svc.evaluate("/opt/unknown/file.txt", "read")
    assert check.allowed is False
    assert check.resolved_permission == "blocked"


def test_scratch_permission_allows_create_and_delete(tmp_path: Path) -> None:
    svc = PathPolicyService(_policy_file(tmp_path))
    assert svc.evaluate("/tmp/ws/scratch/a.txt", "create_file").allowed is True
    assert svc.evaluate("/tmp/ws/scratch/a.txt", "delete").allowed is True


def test_blocked_pattern_wins(tmp_path: Path) -> None:
    svc = PathPolicyService(_policy_file(tmp_path))
    check = svc.evaluate("/tmp/ws/my/.env", "read")
    assert check.allowed is False
    assert check.resolved_permission == "blocked"


def test_real_policy_allows_coolify_server_repo() -> None:
    svc = PathPolicyService(Path(__file__).resolve().parents[1] / "app" / "security" / "path_policy.yaml")
    check = svc.evaluate("/home/juan/Documents/coolify-server", "execute")
    assert check.allowed is True


def test_real_policy_allows_container_runtime_logs() -> None:
    svc = PathPolicyService(Path(__file__).resolve().parents[1] / "app" / "security" / "path_policy.yaml")
    check = svc.evaluate("/app/data/logs/task_x.out.log", "create_file")
    assert check.allowed is True

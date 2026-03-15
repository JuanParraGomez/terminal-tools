from pathlib import Path

import pytest

from app.security.path_policy_service import PathPolicyService
from app.security.validator import SecurityError, SecurityValidator


def _validator() -> SecurityValidator:
    base = Path(__file__).resolve().parents[1] / "app"
    path_policy = PathPolicyService(base / "security" / "path_policy.yaml")
    return SecurityValidator(base, [Path("/home/juan/Documents"), Path("/tmp")], [Path("/home/juan/Documents/scripts/backup")], path_policy)


def test_blocks_sudo_command() -> None:
    v = _validator()
    with pytest.raises(SecurityError):
        v.validate_command(["sudo", "ls"], cwd=Path("/tmp"), allow_mutative=False)


def test_blocks_outside_workdir() -> None:
    v = _validator()
    with pytest.raises(SecurityError):
        v.validate_cwd(Path("/etc"))


def test_blocks_blocked_path_access() -> None:
    v = _validator()
    with pytest.raises(SecurityError):
        v.validate_command(["cat", "/home/juan/Documents/.env"], cwd=Path("/tmp"), allow_mutative=False)


def test_allows_read_only_python_validation_command() -> None:
    v = _validator()
    command = [
        "python3",
        "-c",
        "from pathlib import Path; required=['README.md','app.meta.yaml','deploy.meta.yaml']; missing=[x for x in required if not Path(x).exists()]; print('ok' if not missing else missing)",
    ]
    v.validate_command(command, cwd=Path("/home/juan/Documents/coolify-server"), allow_mutative=False)

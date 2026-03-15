from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.security.path_policy_service import PathPolicyService


class SecurityError(ValueError):
    pass


class SecurityValidator:
    def __init__(
        self,
        base_dir: Path,
        allowed_workdirs: list[Path],
        allowed_script_dirs: list[Path],
        path_policy: PathPolicyService,
    ) -> None:
        self._allow_data = yaml.safe_load((base_dir / "security" / "command_allowlist.yaml").read_text(encoding="utf-8"))
        self._deny_data = yaml.safe_load((base_dir / "security" / "command_denylist.yaml").read_text(encoding="utf-8"))
        self._allowed_commands = set(self._allow_data.get("allowed_commands", []))
        self._deny_commands = set(self._deny_data.get("deny_commands", []))
        self._deny_patterns = [re.compile(p, flags=re.IGNORECASE) for p in self._deny_data.get("forbidden_patterns", [])]
        self._allowed_workdirs = [p.resolve() for p in allowed_workdirs]
        self._allowed_script_dirs = [p.resolve() for p in allowed_script_dirs]
        self._path_policy = path_policy

    def validate_command(self, command: list[str], cwd: Path | None, allow_mutative: bool) -> None:
        if not command:
            raise SecurityError("command is empty")
        exe = command[0]
        inner_command = command
        if exe == "env":
            inner_command = self._unwrap_env_command(command)
            exe = inner_command[0]
        if exe in self._deny_commands:
            raise SecurityError(f"command '{exe}' is blocked")
        if exe not in self._allowed_commands:
            raise SecurityError(f"command '{exe}' is not in allowlist")

        rendered = " ".join(inner_command)
        for pattern in self._deny_patterns:
            if pattern.search(rendered):
                raise SecurityError("command matches a forbidden pattern")

        if not allow_mutative and self._looks_mutative(exe, inner_command):
            raise SecurityError("mutative command requires explicit confirmation")

        if cwd is not None:
            self.validate_cwd(cwd)

        # Validate explicit path-like args against policy.
        for arg in inner_command[1:]:
            if arg.startswith("-"):
                continue
            if "/" not in arg and not arg.startswith("."):
                continue
            candidate = (cwd / arg).resolve() if cwd and not arg.startswith("/") else Path(arg).expanduser().resolve()
            action = "read"
            if exe in {"rm"}:
                action = "delete"
            elif exe in {"chmod"}:
                action = "write"
            elif exe in {"bash", "sh"}:
                action = "execute"
            decision = self._path_policy.evaluate(candidate, action)
            if not decision.allowed:
                raise SecurityError(f"path policy denied {action} on '{candidate}': {decision.reason}")

    def _unwrap_env_command(self, command: list[str]) -> list[str]:
        if len(command) < 2:
            raise SecurityError("env wrapper missing inner command")
        index = 1
        while index < len(command) and "=" in command[index] and not command[index].startswith("-"):
            index += 1
        if index >= len(command):
            raise SecurityError("env wrapper missing executable")
        return command[index:]

    def validate_script_path(self, script_path: Path, allow_mutative: bool) -> None:
        resolved = script_path.resolve()
        if not any(self._is_subpath(resolved, base) for base in self._allowed_script_dirs):
            raise SecurityError("script path is outside allowed script dirs")
        if not resolved.exists() or not resolved.is_file():
            raise SecurityError("script does not exist")
        exec_decision = self._path_policy.evaluate(resolved, "execute")
        if not exec_decision.allowed:
            raise SecurityError(f"path policy denied script execute: {exec_decision.reason}")
        if not allow_mutative:
            text = resolved.read_text(encoding="utf-8", errors="ignore")
            if self._contains_mutative_pattern(text):
                raise SecurityError("script appears mutative and requires explicit confirmation")

    def validate_cwd(self, cwd: Path) -> None:
        resolved = cwd.resolve()
        if not any(self._is_subpath(resolved, base) for base in self._allowed_workdirs):
            raise SecurityError("cwd is outside allowed workdirs")
        decision = self._path_policy.evaluate(resolved, "execute")
        if not decision.allowed:
            raise SecurityError(f"path policy denied cwd usage: {decision.reason}")

    def _looks_mutative(self, exe: str, args: list[str]) -> bool:
        if exe in {"rm", "mv", "cp", "chmod"}:
            return True

        # Allow simple read-only inline validation scripts. The previous
        # substring-based heuristic falsely blocked commands that merely
        # referenced files like deploy.meta.yaml.
        if exe in {"python", "python3"} and "-c" in args:
            rendered = " ".join(args)
            risky_markers = [
                "unlink(",
                "rmtree(",
                "mkdir(",
                "write_text(",
                "write_bytes(",
                "open(",
                "subprocess",
                "os.remove",
                "os.rmdir",
                "os.makedirs",
                "shutil.move",
                "shutil.copy",
                "shutil.rmtree",
            ]
            return any(marker in rendered for marker in risky_markers)

        mutative_patterns: dict[str, set[str]] = {
            "git": {"commit", "push", "pull", "merge", "rebase", "checkout", "switch", "tag", "reset", "clean", "apply", "stash"},
            "docker": {"build", "run", "compose", "rm", "rmi", "stop", "start", "restart"},
            "kubectl": {"apply", "delete", "patch", "scale", "rollout", "set"},
            "terraform": {"apply", "destroy", "taint", "import"},
            "gcloud": {"deploy", "create", "delete", "update", "set"},
        }
        if exe in mutative_patterns:
            return any(arg in mutative_patterns[exe] for arg in args[1:] if not arg.startswith("-"))

        return False

    def _contains_mutative_pattern(self, text: str) -> bool:
        lowered = text.lower()
        return any(x in lowered for x in ["rm -rf", "kubectl apply", "gcloud run deploy", "terraform apply", "chmod"])

    @staticmethod
    def _is_subpath(path: Path, base: Path) -> bool:
        try:
            path.relative_to(base)
            return True
        except ValueError:
            return False

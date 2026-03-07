from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml

from app.models.schemas import PathAccessCheckResponse, PathPermission, PathRule


@dataclass
class _RuleMatch:
    rule: PathRule
    score: int


class PathPolicyService:
    def __init__(self, policy_file: Path) -> None:
        self.policy_file = policy_file
        self._raw = yaml.safe_load(policy_file.read_text(encoding="utf-8")) or {}
        self.defaults = self._raw.get("defaults", {"unknown_paths": "blocked", "follow_symlinks": False})
        self.workspaces = self._raw.get("workspaces", [])
        self.protected = [PathRule(**r) for r in self._raw.get("protected", [])]

    def summary(self) -> dict[str, Any]:
        return {
            "unknown_paths": self.defaults.get("unknown_paths", "blocked"),
            "follow_symlinks": bool(self.defaults.get("follow_symlinks", False)),
            "workspaces": self.workspaces,
            "protected": [r.model_dump() for r in self.protected],
        }

    def blocked_patterns(self) -> list[str]:
        return [r.path for r in self.protected if r.is_pattern]

    def evaluate(self, path: Path | str, action: str) -> PathAccessCheckResponse:
        target = self._normalize(path)
        follow_symlinks = bool(self.defaults.get("follow_symlinks", False))
        if target.is_symlink() and not follow_symlinks:
            return self._deny(target, action, "blocked", None, "symlinks are not allowed by policy")

        protected_match = self._match_rules(target, self.protected, workspace=None)
        if protected_match:
            return self._deny(target, action, "blocked", protected_match.rule, "protected rule matched")

        candidates: list[_RuleMatch] = []
        for ws in self.workspaces:
            ws_name = ws.get("name")
            for rule_data in ws.get("rules", []):
                rule = PathRule(workspace=ws_name, **rule_data)
                matched = self._match_rule(target, rule)
                if matched:
                    candidates.append(matched)

        if not candidates:
            unknown = self.defaults.get("unknown_paths", "blocked")
            return self._deny(target, action, unknown, None, "no matching rule; unknown path policy applied")

        selected = sorted(candidates, key=lambda m: (m.score, self._restrictiveness(m.rule.permission)), reverse=True)[0]
        return self._decide(target, action, selected.rule)

    def render_summary_for_context(self, task_id: str | None = None, preferred_root: str | None = None) -> dict[str, Any]:
        read_write_roots: list[str] = []
        scratch_roots: list[str] = []
        for ws in self.workspaces:
            for rule in ws.get("rules", []):
                permission = rule.get("permission")
                if permission == "read_write":
                    read_write_roots.append(rule["path"])
                if permission == "scratch":
                    scratch_roots.append(rule["path"])
        scratch_root: str | None = None
        if preferred_root:
            for candidate in scratch_roots:
                if candidate.startswith(preferred_root):
                    scratch_root = candidate
                    break
        if scratch_root is None and scratch_roots:
            scratch_root = scratch_roots[0]
        if task_id and scratch_root:
            scratch_root = str(Path(scratch_root) / task_id)
        return {
            "read_write_roots": sorted(set(read_write_roots)),
            "scratch_root": scratch_root,
            "scratch_roots": sorted(set(scratch_roots)),
            "blocked_patterns": self.blocked_patterns(),
        }

    def _decide(self, target: Path, action: str, rule: PathRule) -> PathAccessCheckResponse:
        permission = rule.permission
        if permission == "blocked":
            return self._deny(target, action, permission, rule, "blocked by policy")

        allowed = False
        reason = "action not allowed by permission"

        if permission == "read_only":
            allowed = action == "read"
            reason = "read_only path"
        elif permission == "create_only":
            allowed = action in {"create_file", "create_dir"}
            reason = "create_only path"
        elif permission in {"read_write", "scratch"}:
            if action in {"read", "write"}:
                allowed = True
                reason = f"{permission} permits read/write"
            elif action == "create_file":
                allowed = bool(rule.allow_create_files)
                reason = f"allow_create_files={rule.allow_create_files}"
            elif action == "create_dir":
                allowed = bool(rule.allow_create_dirs)
                reason = f"allow_create_dirs={rule.allow_create_dirs}"
            elif action == "delete":
                allowed = bool(rule.allow_delete)
                reason = f"allow_delete={rule.allow_delete}"
            elif action == "execute":
                allowed = bool(rule.allow_execute)
                reason = f"allow_execute={rule.allow_execute}"

        return PathAccessCheckResponse(
            path=str(target),
            action=action,  # type: ignore[arg-type]
            resolved_permission=permission,
            allowed=allowed,
            matched_rule=rule,
            reason=reason,
        )

    def _deny(self, target: Path, action: str, permission: str, rule: PathRule | None, reason: str) -> PathAccessCheckResponse:
        return PathAccessCheckResponse(
            path=str(target),
            action=action,  # type: ignore[arg-type]
            resolved_permission=permission,  # type: ignore[arg-type]
            allowed=False,
            matched_rule=rule,
            reason=reason,
        )

    def _match_rules(self, target: Path, rules: list[PathRule], workspace: str | None) -> _RuleMatch | None:
        matches = [m for r in rules if (m := self._match_rule(target, r))]
        if not matches:
            return None
        return sorted(matches, key=lambda m: (m.score, self._restrictiveness(m.rule.permission)), reverse=True)[0]

    def _match_rule(self, target: Path, rule: PathRule) -> _RuleMatch | None:
        path_str = str(target)
        rule_path = rule.path
        if rule.is_pattern:
            if fnmatch(path_str, rule_path):
                return _RuleMatch(rule=rule, score=50 + len(rule_path))
            return None

        rule_p = Path(rule_path)
        if target == rule_p:
            return _RuleMatch(rule=rule, score=1000 + len(rule_path))
        try:
            target.relative_to(rule_p)
            return _RuleMatch(rule=rule, score=500 + len(rule_path))
        except ValueError:
            return None

    @staticmethod
    def _normalize(path: Path | str) -> Path:
        if isinstance(path, Path):
            return path.expanduser().resolve()
        return Path(path).expanduser().resolve()

    @staticmethod
    def _restrictiveness(permission: PathPermission) -> int:
        order = {
            "blocked": 5,
            "read_only": 4,
            "create_only": 3,
            "scratch": 2,
            "read_write": 1,
        }
        return order.get(permission, 0)

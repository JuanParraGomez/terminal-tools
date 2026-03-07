from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_secrets(text: str) -> str:
    patterns = [
        re.compile(r"(sk-[A-Za-z0-9_-]{20,})"),
        re.compile(r"(AIza[0-9A-Za-z-_]{20,})"),
        re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s]+)"),
        re.compile(r"(?i)(token\s*[=:]\s*)([^\s]+)"),
    ]
    result = text
    for pat in patterns:
        result = pat.sub(lambda m: (m.group(1) if m.lastindex and m.lastindex > 1 else "") + "***", result)
    return result


def safe_env_metadata() -> dict[str, str]:
    blocked_keys = {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "TOKEN", "PASSWORD", "SECRET"}
    out: dict[str, str] = {}
    for k, v in os.environ.items():
        if any(b in k.upper() for b in blocked_keys):
            continue
        if len(v) > 120:
            out[k] = v[:117] + "..."
        else:
            out[k] = v
    return out


def ensure_within(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False

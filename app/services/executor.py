from __future__ import annotations

import subprocess
import os
from pathlib import Path
from typing import Any

from app.core.utils import mask_secrets


class CommandExecutor:
    def __init__(self, default_timeout_seconds: int, max_output_chars: int) -> None:
        self._timeout = default_timeout_seconds
        self._max_output_chars = max_output_chars

    def run(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout_seconds: int | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        timeout = timeout_seconds or self._timeout
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)
        proc = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
            env=proc_env,
        )
        stdout = mask_secrets(proc.stdout or "")[: self._max_output_chars]
        stderr = mask_secrets(proc.stderr or "")[: self._max_output_chars]
        return {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "ok": proc.returncode == 0,
        }

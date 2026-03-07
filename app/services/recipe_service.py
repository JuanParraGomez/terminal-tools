from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class RecipeService:
    def __init__(self, recipes_dir: Path) -> None:
        self.recipes_dir = recipes_dir
        self._recipes: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        self._recipes.clear()
        for path in self.recipes_dir.rglob("*.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            name = data.get("name")
            if name:
                self._recipes[name] = data

    def get(self, name: str) -> dict[str, Any] | None:
        return self._recipes.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._recipes.keys())

    def render_command(self, name: str, args: dict[str, str]) -> list[str]:
        recipe = self.get(name)
        if not recipe:
            raise ValueError("recipe not found")
        cmd = list(recipe.get("command_base", []))
        for item in recipe.get("args", []):
            value = item
            for key, val in args.items():
                value = value.replace("{" + key + "}", str(val))
            if "{" in value and "}" in value:
                raise ValueError(f"missing placeholder in recipe arg '{item}'")
            cmd.append(value)
        return cmd

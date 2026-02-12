from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from ..errors import NotFoundError, ValidationError


class RulesetLoader:
    def __init__(self, ruleset_dir: Path) -> None:
        self.ruleset_dir = ruleset_dir

    def load(self, ruleset_name: str) -> dict[str, Any]:
        path = self.ruleset_dir / f"{ruleset_name}.json"
        if not path.exists():
            raise NotFoundError("Ruleset not found", {"ruleset": ruleset_name, "path": str(path)})
        data = json.loads(path.read_text(encoding="utf-8"))
        if "rules" not in data or not isinstance(data["rules"], list):
            raise ValidationError("Invalid ruleset format", {"ruleset": ruleset_name})
        return data

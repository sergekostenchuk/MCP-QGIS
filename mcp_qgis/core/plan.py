from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from jsonschema import Draft202012Validator


class PlanValidator:
    def __init__(self, schema_path: Path) -> None:
        self.schema_path = schema_path
        self.validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))

    def validate(self, plan: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
        errors = []
        for err in self.validator.iter_errors(plan):
            errors.append({"message": err.message, "path": list(err.path)})
        return len(errors) == 0, errors

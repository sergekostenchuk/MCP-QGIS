from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaError

from .errors import ValidationError, PreconditionError


def _load_schema(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PreconditionError("Schema file is missing", {"path": str(path)})
    return json.loads(path.read_text(encoding="utf-8"))


class EnvelopeValidator:
    def __init__(self, schema_path: Path, expected_api_version: str) -> None:
        self._schema_path = schema_path
        self._validator = Draft202012Validator(_load_schema(schema_path))
        self._expected_api_version = expected_api_version

    def validate(self, data: dict[str, Any]) -> None:
        errors = sorted(self._validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            err = errors[0]
            raise ValidationError(
                "Envelope validation failed",
                {
                    "message": err.message,
                    "path": list(err.path),
                    "schema_path": str(self._schema_path),
                },
            )
        if data.get("api_version") != self._expected_api_version:
            raise PreconditionError(
                "Unsupported api_version",
                {
                    "expected": self._expected_api_version,
                    "got": data.get("api_version"),
                },
            )


def success_envelope(api_version: str, request_id: str, result: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "api_version": api_version,
        "request_id": request_id,
        "status": "ok",
        "warnings": warnings or [],
        "result": result,
    }


def error_envelope(api_version: str, request_id: str, code: str, message: str, details: dict[str, Any], retryable: bool = False) -> dict[str, Any]:
    return {
        "api_version": api_version,
        "request_id": request_id,
        "status": "error",
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "retryable": retryable,
        },
    }

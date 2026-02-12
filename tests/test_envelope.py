from __future__ import annotations

from pathlib import Path

from mcp_qgis.config import load_settings
from mcp_qgis.envelope import EnvelopeValidator
from mcp_qgis.errors import ValidationError, PreconditionError


def _validator() -> EnvelopeValidator:
    root = Path(__file__).resolve().parents[1]
    settings = load_settings()
    return EnvelopeValidator(root / "schemas" / "mcp-tools.schema.json", settings.api_version)


def test_envelope_valid() -> None:
    v = _validator()
    v.validate(
        {
            "api_version": "1.0.0",
            "request_id": "a233a6ea-2819-4526-a71a-321c61d5f7f5",
            "session_id": "e8f1dbf3-6ec0-492f-8d2d-f1979bbd7540",
            "tool": "project_state",
            "payload": {},
        }
    )


def test_envelope_missing_payload() -> None:
    v = _validator()
    try:
        v.validate(
            {
                "api_version": "1.0.0",
                "request_id": "a233a6ea-2819-4526-a71a-321c61d5f7f5",
                "session_id": "e8f1dbf3-6ec0-492f-8d2d-f1979bbd7540",
                "tool": "project_state",
            }
        )
        assert False, "Expected ValidationError"
    except ValidationError:
        assert True


def test_envelope_bad_api_version() -> None:
    v = _validator()
    try:
        v.validate(
            {
                "api_version": "2.0.0",
                "request_id": "a233a6ea-2819-4526-a71a-321c61d5f7f5",
                "session_id": "e8f1dbf3-6ec0-492f-8d2d-f1979bbd7540",
                "tool": "project_state",
                "payload": {},
            }
        )
        assert False, "Expected PreconditionError"
    except PreconditionError:
        assert True

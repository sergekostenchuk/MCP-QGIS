from __future__ import annotations

from mcp_qgis.cli import cmd_check_config, cmd_doctor


def test_check_config_ok() -> None:
    assert cmd_check_config() == 0


def test_doctor_ok() -> None:
    assert cmd_doctor() == 0

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    api_version: str
    profile: str
    data_root: Path
    log_level: str
    enable_execute_code: bool
    allowed_algorithms_file: Path | None
    host: str
    port: int


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    profile = os.getenv("MCP_PROFILE", "local")
    defaults = {
        "local": {"host": "127.0.0.1", "port": "8765", "log_level": "INFO"},
        "server": {"host": "0.0.0.0", "port": "8080", "log_level": "INFO"},
    }.get(profile, {"host": "127.0.0.1", "port": "8765", "log_level": "INFO"})

    data_root = Path(os.getenv("MCP_DATA_ROOT", str(Path.cwd() / "runtime"))).expanduser()
    allowed_path = os.getenv("MCP_ALLOWED_ALGORITHMS_FILE")
    return Settings(
        api_version=os.getenv("MCP_API_VERSION", "1.0.0"),
        profile=profile,
        data_root=data_root,
        log_level=os.getenv("MCP_LOG_LEVEL", defaults["log_level"]),
        enable_execute_code=_as_bool(os.getenv("MCP_ENABLE_EXECUTE_CODE"), False),
        allowed_algorithms_file=Path(allowed_path).expanduser() if allowed_path else None,
        host=os.getenv("MCP_HOST", defaults["host"]),
        port=int(os.getenv("MCP_PORT", defaults["port"])),
    )


def ensure_runtime_dirs(settings: Settings) -> None:
    for rel in ["artifacts", "logs", "state", "backups"]:
        (settings.data_root / rel).mkdir(parents=True, exist_ok=True)

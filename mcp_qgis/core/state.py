from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProjectState:
    project_id: str
    project_path: str
    crs: str = "EPSG:32637"
    dirty: bool = False
    read_only: bool = False
    layer_count: int = 0
    active_transaction: str | None = None
    adapter_mode: str = "mock"
    bridge_host: str | None = None
    bridge_port: int | None = None
    layer_aliases: dict[str, str] = field(default_factory=dict)


@dataclass
class VariantState:
    variant_id: str
    name: str
    description: str
    created_from: str


@dataclass
class RuntimeState:
    project: ProjectState | None = None
    variants: dict[str, VariantState] = field(default_factory=dict)
    tx_events: list[dict[str, Any]] = field(default_factory=list)

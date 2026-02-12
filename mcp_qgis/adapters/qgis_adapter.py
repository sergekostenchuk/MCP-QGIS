from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class QGISAdapter:
    """MVP adapter stub. Real QGIS calls are implemented in next iterations."""

    mode: str = "mock"

    def run_algorithm(self, algorithm: str, parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "algorithm": algorithm,
            "parameters": parameters,
            "mode": self.mode,
            "status": "simulated",
        }

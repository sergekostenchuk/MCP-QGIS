from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from mcp_qgis.variants import compare_variants, write_variant_report


def test_compare_variants_with_tiebreaker() -> None:
    result = compare_variants(
        variant_ids=["v1", "v2"],
        weights={"lot_count": 0.5, "avg_lot_area": 0.5},
        variant_metrics={
            "v1": {"lot_count": 10, "avg_lot_area": 350, "regulatory_penalty": 1, "utility_length": 120},
            "v2": {"lot_count": 10, "avg_lot_area": 350, "regulatory_penalty": 0, "utility_length": 100},
        },
    )
    assert result["winner_variant_id"] == "v2"


def test_write_variant_report_files() -> None:
    with TemporaryDirectory() as td:
        res = {
            "winner_variant_id": "v1",
            "scores": [
                {"rank": 1, "variant_id": "v1", "score": 0.9, "metrics": {}},
                {"rank": 2, "variant_id": "v2", "score": 0.7, "metrics": {}},
            ],
        }
        json_path, md_path = write_variant_report(res, Path(td))
        assert json_path.exists()
        assert md_path.exists()

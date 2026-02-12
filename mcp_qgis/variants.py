from __future__ import annotations

from pathlib import Path
from typing import Any
import json


COST_METRICS = {"utility_length", "regulatory_penalty"}


def _normalize(values: list[float], is_cost: bool) -> list[float]:
    mx = max(values)
    mn = min(values)
    if mx == mn:
        return [1.0 for _ in values]
    if is_cost:
        return [(mx - v) / (mx - mn) for v in values]
    return [(v - mn) / (mx - mn) for v in values]


def compare_variants(
    variant_ids: list[str],
    weights: dict[str, float],
    variant_metrics: dict[str, dict[str, float]],
) -> dict[str, Any]:
    for vid in variant_ids:
        variant_metrics.setdefault(vid, {})
        for metric in weights:
            variant_metrics[vid].setdefault(metric, 0.0)

    scores: dict[str, float] = {vid: 0.0 for vid in variant_ids}
    for metric, weight in weights.items():
        vals = [float(variant_metrics[vid].get(metric, 0.0)) for vid in variant_ids]
        norm = _normalize(vals, is_cost=metric in COST_METRICS)
        for idx, vid in enumerate(variant_ids):
            scores[vid] += weight * norm[idx]

    ranked = sorted(
        [
            {
                "variant_id": vid,
                "score": round(scores[vid], 6),
                "metrics": variant_metrics[vid],
            }
            for vid in variant_ids
        ],
        key=lambda x: (-x["score"], x["metrics"].get("regulatory_penalty", 0), x["metrics"].get("utility_length", 0), x["variant_id"]),
    )
    for idx, r in enumerate(ranked, start=1):
        r["rank"] = idx

    winner = ranked[0]["variant_id"]
    return {"winner_variant_id": winner, "scores": ranked}


def write_variant_report(compare_result: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "variant-compare.json"
    md_path = output_dir / "variant-compare.md"

    json_path.write_text(json.dumps(compare_result, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Variant Compare Report",
        "",
        f"Winner: `{compare_result['winner_variant_id']}`",
        "",
        "## Scores",
        "",
        "| Rank | Variant | Score |",
        "|---|---|---|",
    ]
    for row in compare_result["scores"]:
        lines.append(f"| {row['rank']} | {row['variant_id']} | {row['score']:.6f} |")

    lines.append("\n## Why Winner\n")
    lines.append("Winner has highest weighted score with tie-breakers applied.")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path

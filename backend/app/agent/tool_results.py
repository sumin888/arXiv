"""Results comparison tool: parse experiment output and diff against reported metrics."""
from __future__ import annotations

import re

SCHEMA = {
    "name": "compare_results",
    "description": (
        "Parse numeric metrics from experiment output and compare them against "
        "reported numbers from the paper. Highlights matches and discrepancies. "
        "Call this after execute_python to verify replication fidelity."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reported": {
                "type": "string",
                "description": (
                    "Text containing the paper's reported metrics "
                    "(e.g. 'accuracy: 0.923, F1: 0.891, BLEU: 34.5')"
                ),
            },
            "actual_output": {
                "type": "string",
                "description": "Raw stdout/output from the experiment run.",
            },
        },
        "required": ["reported", "actual_output"],
    },
}

# Matches patterns like: name = 0.95, name: 0.95, name@5 = 0.8
_METRIC_RE = re.compile(
    r"([\w][\w\-@/]*)\s*[=:]\s*([\d]+\.[\d]+|[\d]+)",
    re.IGNORECASE,
)


def _extract_metrics(text: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for name, val in _METRIC_RE.findall(text):
        try:
            metrics[name.lower()] = float(val)
        except ValueError:
            pass
    return metrics


async def compare_results(reported: str, actual_output: str) -> str:
    rep_m = _extract_metrics(reported)
    act_m = _extract_metrics(actual_output)

    if not rep_m and not act_m:
        return (
            "Could not extract numeric metrics from either source. "
            "Try formatting as 'metric_name: value' (e.g. 'accuracy: 0.923')."
        )

    lines = ["## Results Comparison", ""]
    all_keys = sorted(set(rep_m) | set(act_m))

    for key in all_keys:
        rep = rep_m.get(key)
        act = act_m.get(key)
        if rep is not None and act is not None:
            diff = act - rep
            pct = (diff / rep * 100) if rep != 0 else float("inf")
            tag = "✓ MATCH" if abs(pct) < 1.0 else ("▲" if diff > 0 else "▼")
            lines.append(
                f"  {key}: reported={rep:.4f}  actual={act:.4f}  "
                f"Δ={diff:+.4f} ({pct:+.1f}%)  {tag}"
            )
        elif rep is not None:
            lines.append(f"  {key}: reported={rep:.4f}  actual=NOT FOUND")
        else:
            lines.append(f"  {key}: reported=NOT FOUND  actual={act:.4f}")

    return "\n".join(lines)

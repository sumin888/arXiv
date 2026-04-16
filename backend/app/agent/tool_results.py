"""Results comparison tool: auto-extract paper metrics via RAG, then diff against experiment output."""
from __future__ import annotations

import re
from typing import Awaitable, Callable

SCHEMA = {
    "name": "compare_results",
    "description": (
        "Compare experiment output against reported metrics from the paper. "
        "Automatically extracts the paper's reported numbers via RAG — you only need "
        "to supply the raw output from the experiment run. "
        "Optionally pass `reported` to override with specific numbers. "
        "Call this after run_experiment or execute_python to verify replication fidelity."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "actual_output": {
                "type": "string",
                "description": "Raw stdout/output from the experiment run.",
            },
            "reported": {
                "type": "string",
                "description": (
                    "Optional. Text containing the paper's reported metrics "
                    "(e.g. 'accuracy: 0.923, F1: 0.891'). "
                    "If omitted, metrics are auto-extracted from the paper via RAG."
                ),
            },
        },
        "required": ["actual_output"],
    },
}

# Matches patterns like: name = 0.95, name: 0.95, name@5 = 0.8
_METRIC_RE = re.compile(
    r"([\w][\w\-@/]*)\s*[=:]\s*([\d]+\.[\d]+|[\d]+)",
    re.IGNORECASE,
)

# RAG queries to locate result tables / metric sections in the paper
_RAG_QUERIES = [
    "reported results metrics accuracy F1 performance table",
    "experimental results baseline comparison BLEU ROUGE precision recall",
    "quantitative evaluation benchmark scores",
]


def _extract_metrics(text: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for name, val in _METRIC_RE.findall(text):
        try:
            metrics[name.lower()] = float(val)
        except ValueError:
            pass
    return metrics


def make_compare_results(
    rag_fetcher: Callable[[str], Awaitable[str]] | None = None,
):
    """Return a compare_results callable, optionally bound to a RAG search function."""

    async def compare_results(actual_output: str, reported: str = "") -> str:
        # Auto-fetch from paper if `reported` not supplied
        if not reported.strip() and rag_fetcher is not None:
            rag_parts: list[str] = []
            for q in _RAG_QUERIES:
                try:
                    chunk = await rag_fetcher(q)
                    if chunk and "No relevant passages" not in chunk:
                        rag_parts.append(chunk)
                except Exception:
                    pass
            reported = "\n\n".join(rag_parts)

        rep_m = _extract_metrics(reported)
        act_m = _extract_metrics(actual_output)

        if not rep_m and not act_m:
            return (
                "Could not extract numeric metrics from either source. "
                "Try formatting as 'metric_name: value' (e.g. 'accuracy: 0.923') "
                "or pass the relevant paper excerpt as `reported`."
            )

        lines = ["## Results Comparison", ""]

        if not rep_m:
            lines.append(
                "_Paper metrics not found via RAG — pass the relevant section as `reported`._\n"
            )
        if not act_m:
            lines.append(
                "_No numeric metrics detected in experiment output._\n"
            )

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

    return compare_results


# Standalone version (no RAG) kept for backward compatibility
async def compare_results(reported: str, actual_output: str) -> str:
    fn = make_compare_results(rag_fetcher=None)
    return await fn(actual_output=actual_output, reported=reported)

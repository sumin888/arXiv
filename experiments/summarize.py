"""
Read results JSON files and print a formatted 1-page HW8 summary to stdout.

Usage:
    python experiments/summarize.py
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median, quantiles

RESULTS = Path(__file__).resolve().parent / "results"


def load(name: str) -> list[dict]:
    p = RESULTS / name
    if not p.exists():
        return []
    return json.loads(p.read_text())


def pct(n: int, total: int) -> str:
    return f"{100 * n // total}%" if total else "n/a"


def p95(lats: list[float]) -> float | str:
    return round(quantiles(lats, n=20)[18], 2) if len(lats) >= 5 else "n/a"


def main() -> None:
    exp1 = load("exp1_tool_selection.json")
    exp2 = load("exp2_question_types.json")
    exp3 = load("exp3_concurrency.json")

    print("=" * 60)
    print("  arXiv Agent — HW8 Experiment Summary")
    print("=" * 60)

    # ── Exp 1 ────────────────────────────────────────────────────────────────
    print("\nExperiment 1 — Tool-selection / Grounding (30 concurrent agents)")
    print("  Setup   : 30 paper agents fired simultaneously, same factual question")
    print("  Changed : HW7 ran ≤5 agents sequentially; HW8 runs 30 concurrently")
    if exp1:
        ok   = [r for r in exp1 if r["status"] == "ok"]
        lats = [r["latency_s"] for r in ok]
        domains = {}
        for r in ok:
            domains.setdefault(r["domain"], []).append(r["latency_s"])
        print(f"  Result  : {len(ok)}/30 succeeded  "
              f"p50={round(median(lats),2)}s  p95={p95(lats)}s")
        print(f"            avg reply={round(mean(r['reply_len'] for r in ok))} chars")
        slowest = max(domains, key=lambda d: mean(domains[d]))
        fastest = min(domains, key=lambda d: mean(domains[d]))
        print(f"            slowest domain: {slowest}  fastest: {fastest}")
        failed = [r for r in exp1 if r["status"] != "ok"]
        if failed:
            print(f"  Failures: {[r['arxiv_id'] for r in failed]}")
        print("  Takeaway: [fill in after running — e.g. 'Biology papers timed out more'")
        print("             'because abstracts are shorter, giving the agent less context']")
    else:
        print("  [no results yet — run run_hw8.py --exp 1]")

    # ── Exp 2 ────────────────────────────────────────────────────────────────
    print("\nExperiment 2 — Question-type Stress (90 agent calls)")
    print("  Setup   : factual / methodological / comparative × 30 papers each")
    print("  Changed : HW7 used only factual questions; HW8 adds harder question types")
    if exp2:
        for qtype in ("factual", "methodological", "comparative"):
            batch = [r for r in exp2 if r["question_type"] == qtype]
            ok    = [r for r in batch if r["status"] == "ok"]
            lats  = [r["latency_s"] for r in ok]
            lens  = [r["reply_len"] for r in ok]
            p50   = round(median(lats), 2) if lats else "n/a"
            avg_l = round(mean(lens)) if lens else 0
            print(f"  {qtype:<15} p50={p50}s  avg_reply={avg_l} chars  ok={len(ok)}/30")
        print("  Takeaway: [fill in — e.g. 'Methodological questions took 2× longer")
        print("             and produced 40% longer replies, suggesting more tool calls']")
    else:
        print("  [no results yet — run run_hw8.py --exp 2]")

    # ── Exp 3 ────────────────────────────────────────────────────────────────
    print("\nExperiment 3 — Concurrency Scaling (1 / 10 / 30 workers)")
    print("  Setup   : fixed paper (Attention Is All You Need), vary simultaneous workers")
    print("  Changed : HW7 never tested concurrent load; HW8 stress-tests the backend")
    if exp3:
        for c in (1, 10, 30):
            batch = [r for r in exp3 if r.get("concurrency") == c]
            ok    = [r for r in batch if r["status"] == "ok"]
            lats  = [r["latency_s"] for r in ok]
            wall  = batch[0].get("wall_time_s", "?") if batch else "?"
            p50   = round(median(lats), 2) if lats else "n/a"
            errs  = len(batch) - len(ok)
            print(f"  concurrency={c:<3}  wall={wall}s  p50={p50}s  errors={errs}/{c}")
        print("  Takeaway: [fill in — e.g. 'p95 latency tripled from 1→30 workers;")
        print("             2 requests timed out at concurrency=30']")
    else:
        print("  [no results yet — run run_hw8.py --exp 3]")

    print("\n" + "=" * 60)
    print("  Key Takeaways (fill in after running)")
    print("=" * 60)
    print("  1. Success rate at 30 concurrent agents: ___")
    print("  2. Latency degradation 1→30 workers:     ___")
    print("  3. Hardest question type:                ___")
    print("  4. Domain with most failures:            ___")
    print("  5. Main bottleneck identified:           ___")
    print()


if __name__ == "__main__":
    main()

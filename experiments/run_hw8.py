"""
HW8 Experiment Runner — 30 concurrent paper agents, local backend.

Usage:
    # Make sure the backend is running: cd backend && uvicorn app.main:app --reload
    python experiments/run_hw8.py [--base-url http://127.0.0.1:8000] [--exp 1|2|3|all]

Experiments
-----------
1  Tool-selection diversity   — same factual question across all 30 papers; measure latency,
                                success rate, and whether the response is grounded in the paper.
2  Question-type stress       — 3 question types (factual / methodological / comparative)
                                across 30 papers; measure how latency and answer length vary.
3  Concurrency scaling        — same question at 1 / 10 / 30 simultaneous workers;
                                measure p50, p95 latency and error rate.

All results are written to experiments/results/ as JSON + a printed summary table.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from statistics import mean, median, quantiles
from typing import Any

import httpx

# ── Resolve project root regardless of where the script is run from ──────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "experiments"))

from papers import PAPERS, QUESTIONS  # noqa: E402

RESULTS_DIR = ROOT / "experiments" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL_DEFAULT = "http://127.0.0.1:8000"


# ── HTTP helpers ─────────────────────────────────────────────────────────────

async def index_paper(client: httpx.AsyncClient, arxiv_id: str) -> None:
    """Trigger background indexing; ignore errors (paper may already be indexed)."""
    try:
        await client.post("/index", json={"arxivId": arxiv_id}, timeout=10)
    except Exception:
        pass


async def chat(
    client: httpx.AsyncClient,
    paper: dict,
    question: str,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Send one chat turn and return a result dict with timing + metadata."""
    payload = {
        "arxivId": paper["id"],
        "title": paper["title"],
        "abstract": "",          # no abstract pre-loaded; agent will use RAG
        "messages": [{"role": "user", "content": question}],
        "messageCount": 1,
        "primaryCategory": paper["domain"],
        "activeBridgeId": "",
        "activeBridgeTitle": "",
    }

    t0 = time.perf_counter()
    try:
        resp = await client.post("/chat", json=payload, timeout=timeout)
        elapsed = time.perf_counter() - t0
        if resp.status_code == 200:
            reply = resp.json().get("reply", "")
            return {
                "arxiv_id": paper["id"],
                "domain": paper["domain"],
                "title": paper["title"],
                "question_type": "",        # filled in by caller
                "latency_s": round(elapsed, 3),
                "status": "ok",
                "reply_len": len(reply),
                "reply_snippet": reply[:200].replace("\n", " "),
            }
        else:
            return {
                "arxiv_id": paper["id"],
                "domain": paper["domain"],
                "title": paper["title"],
                "question_type": "",
                "latency_s": round(elapsed, 3),
                "status": f"http_{resp.status_code}",
                "reply_len": 0,
                "reply_snippet": resp.text[:200],
            }
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return {
            "arxiv_id": paper["id"],
            "domain": paper["domain"],
            "title": paper["title"],
            "question_type": "",
            "latency_s": round(elapsed, 3),
            "status": f"error: {type(exc).__name__}",
            "reply_len": 0,
            "reply_snippet": str(exc)[:200],
        }


# ── Experiment 1: Tool-selection / grounding across 30 papers ───────────────

async def run_exp1(client: httpx.AsyncClient) -> list[dict]:
    """Fire the factual question at all 30 papers concurrently."""
    print("\n── Experiment 1: 30 concurrent agents, factual question ──")
    question = QUESTIONS["factual"]

    tasks = [chat(client, p, question) for p in PAPERS]
    results = await asyncio.gather(*tasks)

    for r in results:
        r["question_type"] = "factual"

    _print_exp_summary("Exp 1 — Tool-selection / grounding (30 agents)", results)
    _save(results, "exp1_tool_selection.json")
    return list(results)


# ── Experiment 2: Question-type stress (factual / methodological / comparative)

async def run_exp2(client: httpx.AsyncClient) -> list[dict]:
    """Test all 3 question types across all 30 papers. 90 total agent calls."""
    print("\n── Experiment 2: Question-type stress (90 agent calls) ──")
    all_results: list[dict] = []

    for qtype, question in QUESTIONS.items():
        print(f"   [{qtype}] firing 30 concurrent agents …")
        tasks = [chat(client, p, question) for p in PAPERS]
        batch = await asyncio.gather(*tasks)
        for r in batch:
            r["question_type"] = qtype
        all_results.extend(batch)

    _print_exp2_summary(all_results)
    _save(all_results, "exp2_question_types.json")
    return all_results


# ── Experiment 3: Concurrency scaling (1 / 10 / 30 simultaneous workers) ────

async def run_exp3(client: httpx.AsyncClient) -> list[dict]:
    """
    Use the first paper as a fixed target. Fire it with 1, 10, 30 simultaneous
    workers and record how latency degrades.
    """
    print("\n── Experiment 3: Concurrency scaling (1 / 10 / 30 workers) ──")
    target = PAPERS[0]          # Attention Is All You Need
    question = QUESTIONS["factual"]
    all_results: list[dict] = []

    for concurrency in (1, 10, 30):
        print(f"   concurrency={concurrency} …")
        tasks = [chat(client, target, question) for _ in range(concurrency)]
        t_wall = time.perf_counter()
        batch = await asyncio.gather(*tasks)
        wall = round(time.perf_counter() - t_wall, 3)

        for r in batch:
            r["question_type"] = "factual"
            r["concurrency"] = concurrency
            r["wall_time_s"] = wall
        all_results.extend(batch)

        latencies = [r["latency_s"] for r in batch if r["status"] == "ok"]
        errors    = sum(1 for r in batch if r["status"] != "ok")
        p50 = round(median(latencies), 2) if latencies else None
        p95 = round(quantiles(latencies, n=20)[18], 2) if len(latencies) >= 5 else None
        print(f"     wall={wall}s  p50={p50}s  p95={p95}s  errors={errors}/{concurrency}")

    _print_exp_summary("Exp 3 — Concurrency scaling", all_results)
    _save(all_results, "exp3_concurrency.json")
    return all_results


# ── Printing helpers ─────────────────────────────────────────────────────────

def _print_exp_summary(label: str, results: list[dict]) -> None:
    ok      = [r for r in results if r["status"] == "ok"]
    failed  = [r for r in results if r["status"] != "ok"]
    lats    = [r["latency_s"] for r in ok]

    print(f"\n{'─'*55}")
    print(f"  {label}")
    print(f"{'─'*55}")
    print(f"  Agents run   : {len(results)}")
    print(f"  Success      : {len(ok)}  ({100*len(ok)//len(results)}%)")
    print(f"  Failed       : {len(failed)}")
    if lats:
        print(f"  Latency p50  : {round(median(lats), 2)}s")
        print(f"  Latency mean : {round(mean(lats), 2)}s")
        print(f"  Latency max  : {round(max(lats), 2)}s")
        avg_len = round(mean(r["reply_len"] for r in ok))
        print(f"  Avg reply len: {avg_len} chars")
    if failed:
        print(f"\n  Failures:")
        for r in failed[:5]:
            print(f"    [{r['arxiv_id']}] {r['status']} — {r['reply_snippet'][:80]}")
    print()


def _print_exp2_summary(results: list[dict]) -> None:
    print(f"\n{'─'*55}")
    print("  Exp 2 — Question-type breakdown")
    print(f"{'─'*55}")
    for qtype in ("factual", "methodological", "comparative"):
        batch = [r for r in results if r["question_type"] == qtype]
        ok    = [r for r in batch if r["status"] == "ok"]
        lats  = [r["latency_s"] for r in ok]
        lens  = [r["reply_len"] for r in ok]
        p50   = round(median(lats), 2) if lats else "n/a"
        avg_l = round(mean(lens)) if lens else 0
        print(f"  {qtype:<15}  p50={p50}s   avg_reply={avg_l} chars   ok={len(ok)}/30")
    print()


# ── Persistence ──────────────────────────────────────────────────────────────

def _save(data: list[dict], filename: str) -> None:
    path = RESULTS_DIR / filename
    path.write_text(json.dumps(data, indent=2))
    print(f"  → saved {path}")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main(base_url: str, exp: str) -> None:
    print(f"arXiv HW8 Experiment Runner")
    print(f"Backend : {base_url}")
    print(f"Papers  : {len(PAPERS)} agents")

    # Quick health check
    async with httpx.AsyncClient(base_url=base_url) as client:
        try:
            r = await client.get("/health", timeout=5)
            health = r.json()
            print(f"Health  : {health}")
        except Exception as e:
            print(f"[WARN] Backend not reachable: {e}")
            print("       Start it with: cd backend && uvicorn app.main:app --reload")
            return

        # Pre-index all papers in the background so RAG is ready
        print(f"\nPre-indexing {len(PAPERS)} papers (background) …")
        index_tasks = [index_paper(client, p["id"]) for p in PAPERS]
        await asyncio.gather(*index_tasks)
        print("Indexing triggered. Waiting 3 s before experiments …")
        await asyncio.sleep(3)

        if exp in ("1", "all"):
            await run_exp1(client)
        if exp in ("2", "all"):
            await run_exp2(client)
        if exp in ("3", "all"):
            await run_exp3(client)

    print("Done. Results in experiments/results/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE_URL_DEFAULT)
    parser.add_argument(
        "--exp",
        default="all",
        choices=["1", "2", "3", "all"],
        help="Which experiment to run (default: all)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.base_url, args.exp))

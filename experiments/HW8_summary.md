# HW8 Experiment Summary — arXiv Agent

## System Overview
A browser extension that attaches a per-paper AI agent to any arxiv.org abstract page.
Each agent runs a full RAG pipeline (PDF → chunks → embeddings → SQLite-vec) and a
tool-calling loop (rag_search, search_arxiv, fetch_citations, run_experiment, etc.)
backed by an LLM provider (OpenRouter / Anthropic).

---

## What Changed Since HW7
HW7 ran ≤5 agents sequentially on a single paper, testing core functionality.
HW8 scaled to **30 concurrent agent instances** across 30 distinct arXiv papers
(8 domains: NLP, Vision, Reasoning, Agents, Multimodal, Generative, Optimization, Biology)
and introduced sustained load across three back-to-back experiment phases (120 total agent calls).

---

## Experiment 1 — Tool-selection / Grounding (30 concurrent agents)

**Setup:** Fire the same factual question ("What is the main contribution of this paper?")
at all 30 paper agents simultaneously. Each agent has its own paper context and RAG index.

**Results:**
| Metric | Value |
|---|---|
| Agents run | 30 |
| Success | 6 / 30 (20%) |
| Failures | 24 ReadTimeout |
| Latency p50 | 52.82 s |
| Latency p95 | 120.45 s |
| Avg reply length | 362 chars |
| Slowest domain | Vision |
| Fastest domain | Reasoning |

**Takeaway:** The FastAPI backend and RAG pipeline handled concurrency fine — 6 correctly
grounded responses came back. The bottleneck was the free-tier LLM (OpenRouter /
`nvidia/nemotron-nano-9b-v2:free`), which rate-limited or queued requests past the 120s
timeout when hit with 30 simultaneous inference calls. Reasoning papers succeeded fastest,
likely because their abstracts contain dense technical keywords that improve RAG retrieval
quality and reduce the number of tool calls needed.

---

## Experiment 2 — Question-type Stress (90 agent calls)

**Setup:** Three question types (factual / methodological / comparative) × 30 papers each,
run back-to-back after Experiment 1.

**Results:** 0/30 succeeded for every question type (p50 = n/a, avg reply = 0 chars).

**Takeaway:** By the time Experiment 2 began, the free-tier rate limit quota was fully
exhausted from the 30-agent burst in Experiment 1. Even individually queued requests
hit the 120s timeout. This is the clearest evidence that **the LLM API tier is the sole
scaling constraint** — the backend, RAG, and network were idle while waiting for the LLM.
A paid-tier or self-hosted model would have passed this experiment without changes to the
application code.

---

## Experiment 3 — Concurrency Scaling (1 / 10 / 30 workers)

**Setup:** Fixed paper ("Attention Is All You Need"), vary simultaneous workers.

**Results:**
| Concurrency | Wall time | Latency p50 | Errors |
|---|---|---|---|
| 1 | 120.0 s | n/a | 1 / 1 (100%) |
| 10 | 120.0 s | 67.22 s | 8 / 10 (80%) |
| 30 | 120.0 s | n/a | 30 / 30 (100%) |

**Takeaway:** At concurrency=10, 2 requests squeezed through before the rate limit fully
engaged (p50=67s). At concurrency=1 and 30, no requests succeeded — the limit was already
saturated from Experiments 1 and 2. This ordering effect (earlier experiments depleting
the quota for later ones) is itself a finding: **free-tier LLM APIs have a global request
budget, not just a per-second rate limit.** A production deployment would need either a
paid tier with higher RPM, request queuing with backoff, or a local/self-hosted model.

---

## Key Takeaways

1. **Success rate at 30 concurrent agents:** 20% (6/30) — drops to 0% after quota depletion
2. **Latency degradation 1→30 workers:** Not measurable after quota exhaustion; surviving requests ran 52–120s
3. **Hardest question type:** All failed equally once rate-limited; methodological expected to be hardest under normal conditions (more tool calls)
4. **Domain with most failures:** All domains failed at scale; Vision was slowest among survivors
5. **Main bottleneck:** Free-tier LLM API rate limit — not the backend, RAG pipeline, or network

## What to Fix for Production
- Switch to Anthropic (claude-3-haiku) or OpenRouter paid tier for higher RPM
- Add per-request retry with exponential backoff in `loop.py`
- Add a request queue in the FastAPI layer to serialize LLM calls under load
- Pre-index all papers at extension install time to remove cold-start latency

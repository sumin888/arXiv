"""Model-agnostic tool-calling agent loop.

Supports both Anthropic (native tool use) and OpenRouter (OpenAI-compatible
function calling). The loop runs until the model produces a final text
response or max_iterations is reached.
"""
from __future__ import annotations

import json
import re
import sqlite3

from app.config import settings
from app.agent.registry import ToolRegistry

_SYSTEM = """\
You are an expert AI research assistant helping users understand, reproduce, and \
build on arXiv papers. You have access to several tools — use them proactively:

• rag_search          — search the full text of the current paper (use first for any \
paper-specific question)
• search_arxiv        — find related papers
• fetch_citations     — citation data from Semantic Scholar
• fetch_github_repo   — explore a GitHub repo's metadata, README, and file tree
• run_experiment      — clone a GitHub repo, install deps, find entry point, and run it \
end-to-end to reproduce results
• execute_python      — run arbitrary Python code locally (no repo needed)
• compare_results     — auto-extract reported metrics from the paper via RAG and diff \
against experiment output; only actual_output is required
• sample_bridge_paper — find a paper from a DIFFERENT domain that uses the same core \
methods, surfacing cross-disciplinary connections

Ground every answer in evidence. Cite chunk IDs when quoting the paper.

Current paper: {paper_title}  (arXiv:{arxiv_id})
Abstract: {abstract}"""


# ── Bridge helpers ────────────────────────────────────────────────────────────

_STOP = frozenset(
    "the a an of in to for and with on by is are we our this that which from be "
    "as it its at or has have been was were their can not but they these those each "
    "all also such than into more most both between through over about while show "
    "use used using propose proposed present paper model result results approach "
    "method methods task tasks learn learning based show shows demonstrate".split()
)


def _extract_keywords(abstract: str, n: int = 4) -> list[str]:
    """Pull the first n meaningful words from the abstract for use as bridge keywords."""
    words = re.findall(r"\b[a-zA-Z][a-zA-Z\-]{3,}\b", abstract)
    seen: set[str] = set()
    keywords: list[str] = []
    for w in words:
        lw = w.lower()
        if lw not in _STOP and lw not in seen:
            seen.add(lw)
            keywords.append(w)
        if len(keywords) >= n:
            break
    return keywords


async def _build_bridge_tag(abstract: str, primary_category: str) -> str:
    """Call sample_bridge_paper directly and format the result as a <bridge> XML tag."""
    from app.agent.tool_bridge import sample_bridge_paper

    keywords = _extract_keywords(abstract)
    if not keywords:
        return ""

    try:
        result = await sample_bridge_paper(keywords, primary_category)
    except Exception:
        return ""

    if "No bridge paper" in result or "Could not parse" in result:
        return ""

    # Parse key: value lines from the tool output
    data: dict[str, str] = {}
    for line in result.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            data[k.strip()] = v.strip()

    arxiv_id = data.get("arxiv_id", "")
    title = data.get("title", "")
    domain = data.get("domain", "")
    bridge_reason = data.get("bridge_reason", "")

    if not arxiv_id or not title:
        return ""

    method = keywords[0] if keywords else "similar methods"

    return (
        f'\n\n<bridge arxiv_id="{arxiv_id}">\n'
        f"✦ {title} ({domain}) applies {method} in a different context.\n"
        f"{bridge_reason} Want to explore this?\n"
        f"</bridge>"
    )

# Added to the system prompt when the user is exploring a bridge paper
_BRIDGE_CONTEXT = """\

---
BRIDGE EXPLORATION MODE
The user is now exploring a bridge paper alongside the current paper.
Bridge paper: "{bridge_title}" (arXiv:{bridge_id})

You have RAG excerpts from BOTH papers below. Compare how the shared method is used \
in each context. Offer concrete suggestions for what it would look like to apply \
the bridge paper's approach to the current paper's problem."""


def build_registry(conn: sqlite3.Connection, arxiv_id: str) -> ToolRegistry:
    """Wire all tools into a registry bound to the current paper."""
    from app.agent import (
        tool_arxiv,
        tool_bridge,
        tool_citations,
        tool_execute,
        tool_experiment,
        tool_github,
        tool_rag,
        tool_results,
    )

    registry = ToolRegistry()

    # RAG is bound to the current paper's DB connection and ID
    async def _rag(query: str) -> str:
        return await tool_rag.rag_search(conn, arxiv_id, query)

    registry.register(tool_rag.SCHEMA, _rag)
    registry.register(tool_arxiv.SCHEMA, tool_arxiv.search_arxiv)
    registry.register(tool_citations.SCHEMA, tool_citations.fetch_citations)
    registry.register(tool_github.SCHEMA, tool_github.fetch_github_repo)
    registry.register(tool_experiment.SCHEMA, tool_experiment.run_experiment)
    registry.register(tool_execute.SCHEMA, tool_execute.execute_python)
    registry.register(tool_bridge.SCHEMA, tool_bridge.sample_bridge_paper)

    # compare_results is wired with the RAG fetcher so it auto-extracts paper metrics
    compare_fn = tool_results.make_compare_results(rag_fetcher=_rag)
    registry.register(tool_results.SCHEMA, compare_fn)

    return registry


async def run_agent(
    *,
    conn: sqlite3.Connection,
    arxiv_id: str,
    paper_title: str,
    abstract: str,
    messages: list[dict],
    message_count: int = 0,
    primary_category: str = "",
    active_bridge_id: str = "",
    active_bridge_title: str = "",
    max_iterations: int = 12,
) -> str:
    from app.agent.tool_rag import rag_search
    from app.rag.pipeline import ensure_paper_indexed

    registry = build_registry(conn, arxiv_id)

    # Pre-fetch RAG results for the user's query so the LLM sees paper context
    # on the very first call — this cuts the common case from 2 LLM calls to 1.
    last_user = next(
        (
            m["content"]
            for m in reversed(messages)
            if m.get("role") == "user" and m.get("content", "").strip()
        ),
        "",
    )

    pre_context = ""
    if last_user:
        try:
            pre_context = await rag_search(conn, arxiv_id, last_user)
        except Exception:
            pass  # indexing not yet done; agent will call rag_search itself

    system = _SYSTEM.format(
        paper_title=paper_title or arxiv_id,
        arxiv_id=arxiv_id,
        abstract=(abstract or "(none)")[:800],
    )

    # ── Bridge exploration: dual-paper RAG ────────────────────────────────────
    if active_bridge_id and active_bridge_title:
        system += _BRIDGE_CONTEXT.format(
            bridge_title=active_bridge_title,
            bridge_id=active_bridge_id,
        )

        bridge_context = ""
        if last_user:
            try:
                await ensure_paper_indexed(conn, active_bridge_id)
                bridge_context = await rag_search(conn, active_bridge_id, last_user)
            except Exception:
                pass

        if bridge_context:
            system += (
                f"\n\nBridge paper excerpts ({active_bridge_id}):\n\n" + bridge_context
            )

    # ── Inject pre-fetched main-paper context ─────────────────────────────────
    if pre_context:
        system += (
            "\n\n---\nPre-fetched excerpts from current paper "
            "(use directly if sufficient; call rag_search again only if you need a different angle):\n\n"
            + pre_context
        )

    provider = settings.llm_provider.lower().strip()
    if provider == "anthropic":
        reply = await _loop_anthropic(system, messages, registry, max_iterations)
    elif provider == "openrouter":
        reply = await _loop_openrouter(system, messages, registry, max_iterations)
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")

    # ── Backend-driven bridge injection (every 3rd user message) ─────────────
    # Done here rather than relying on the LLM to call the tool — guarantees
    # the bridge always fires regardless of model quality.
    if message_count > 0 and message_count % 3 == 0 and "<bridge" not in reply:
        bridge_tag = await _build_bridge_tag(abstract or paper_title, primary_category)
        if bridge_tag:
            reply = reply.rstrip() + bridge_tag

    return reply


# ── Anthropic ───────────────────────────────────────────────────────────────

async def _loop_anthropic(
    system: str,
    messages: list[dict],
    registry: ToolRegistry,
    max_iterations: int,
) -> str:
    from anthropic import Anthropic

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = Anthropic(api_key=settings.anthropic_api_key)
    api_msgs: list = _normalize(messages)

    for _ in range(max_iterations):
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=system,
            messages=api_msgs,
            tools=registry.schemas(),  # already in Anthropic format
        )

        if response.stop_reason != "tool_use":
            return "".join(
                b.text for b in response.content if b.type == "text"
            ).strip()

        # Append assistant turn (content blocks) then tool results
        api_msgs.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = await registry.execute(block.name, **block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
        api_msgs.append({"role": "user", "content": tool_results})

    raise RuntimeError("Agent loop exceeded max_iterations without a final answer.")


# ── OpenRouter (OpenAI-compatible) ──────────────────────────────────────────

async def _loop_openrouter(
    system: str,
    messages: list[dict],
    registry: ToolRegistry,
    max_iterations: int,
) -> str:
    from openai import OpenAI

    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    extra: dict[str, str] = {"X-Title": "arXiv Agent"}
    if settings.openrouter_http_referer:
        extra["HTTP-Referer"] = settings.openrouter_http_referer

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        default_headers=extra,
    )
    api_msgs: list = [{"role": "system", "content": system}, *_normalize(messages)]
    tools = _to_openai_tools(registry)

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=api_msgs,
            tools=tools,
            max_tokens=4096,
        )
        choice = response.choices[0]

        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            return (choice.message.content or "").strip()

        api_msgs.append(choice.message)
        for tc in choice.message.tool_calls:
            kwargs = json.loads(tc.function.arguments or "{}")
            result = await registry.execute(tc.function.name, **kwargs)
            api_msgs.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )

    raise RuntimeError("Agent loop exceeded max_iterations without a final answer.")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _normalize(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content})
    return out


def _to_openai_tools(registry: ToolRegistry) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["input_schema"],
            },
        }
        for s in registry.schemas()
    ]

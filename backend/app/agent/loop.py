"""Model-agnostic tool-calling agent loop.

Supports both Anthropic (native tool use) and OpenRouter (OpenAI-compatible
function calling). The loop runs until the model produces a final text
response or max_iterations is reached.
"""
from __future__ import annotations

import json
import sqlite3

from app.config import settings
from app.agent.registry import ToolRegistry

_SYSTEM = """\
You are an expert AI research assistant helping users understand, reproduce, and \
build on arXiv papers. You have access to several tools — use them proactively:

• rag_search        — search the full text of the current paper (use first for any \
paper-specific question)
• search_arxiv      — find related papers
• fetch_citations   — citation data from Semantic Scholar
• fetch_github_repo — explore code repos linked to the paper
• execute_python    — run code in a sandboxed environment (E2B)
• compare_results   — diff experiment output against reported numbers

Ground every answer in evidence. Cite chunk IDs when quoting the paper.

Current paper: {paper_title}  (arXiv:{arxiv_id})
Abstract: {abstract}"""


def build_registry(conn: sqlite3.Connection, arxiv_id: str) -> ToolRegistry:
    """Wire all tools into a registry bound to the current paper."""
    from app.agent import (
        tool_arxiv,
        tool_citations,
        tool_execute,
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
    registry.register(tool_execute.SCHEMA, tool_execute.execute_python)
    registry.register(tool_results.SCHEMA, tool_results.compare_results)

    return registry


async def run_agent(
    *,
    conn: sqlite3.Connection,
    arxiv_id: str,
    paper_title: str,
    abstract: str,
    messages: list[dict],
    max_iterations: int = 12,
) -> str:
    from app.agent.tool_rag import rag_search

    registry = build_registry(conn, arxiv_id)

    # Pre-fetch RAG results for the user's query so the LLM sees paper context
    # on the very first call — this cuts the common case from 2 LLM calls to 1.
    last_user = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user" and m.get("content", "").strip()),
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
    if pre_context:
        system += (
            "\n\n---\nPre-fetched paper excerpts for this query (use directly if sufficient; "
            "call rag_search again only if you need a different angle):\n\n"
            + pre_context
        )

    provider = settings.llm_provider.lower().strip()
    if provider == "anthropic":
        return await _loop_anthropic(system, messages, registry, max_iterations)
    if provider == "openrouter":
        return await _loop_openrouter(system, messages, registry, max_iterations)
    raise RuntimeError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")


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

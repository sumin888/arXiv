from __future__ import annotations

from anthropic import Anthropic
from openai import OpenAI

from app.config import settings


def build_context_block(chunk_bodies: list[tuple[int, str]]) -> str:
    parts = []
    for cid, text in chunk_bodies:
        parts.append(f"[chunk_id={cid}]\n{text}")
    return "\n\n---\n\n".join(parts)


def build_system_prompt(
    *,
    paper_title: str,
    arxiv_id: str,
    abstract: str,
    context_chunks: list[tuple[int, str]],
) -> str:
    context = build_context_block(context_chunks)
    return (
        "You are a research assistant helping the user understand an arXiv paper. "
        "Answer only using information that is supported by the retrieved excerpts below. "
        "If the excerpts do not contain enough information, say so and suggest what "
        "kind of section or keyword might help. "
        "Use clear structure (short paragraphs or bullets). "
        "When citing a claim, mention the chunk_id in parentheses like (chunk_id=42).\n\n"
        f"Paper: {paper_title}\n"
        f"arXiv ID: {arxiv_id}\n"
        f"Abstract (metadata): {abstract or '(none)'}\n\n"
        f"Retrieved excerpts:\n{context}"
    )


def _normalize_messages(messages: list[dict]) -> list[dict]:
    api_messages = []
    for m in messages:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        api_messages.append({"role": role, "content": content})
    if not api_messages or api_messages[-1]["role"] != "user":
        raise ValueError("messages must end with a user turn")
    return api_messages


def _generate_openrouter(
    system: str,
    api_messages: list[dict],
) -> str:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (required when LLM_PROVIDER=openrouter)")
    extra_headers: dict[str, str] = {"X-Title": "arXiv RAG"}
    if settings.openrouter_http_referer:
        extra_headers["HTTP-Referer"] = settings.openrouter_http_referer
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        default_headers=extra_headers,
    )
    chat_messages = [{"role": "system", "content": system}, *api_messages]
    out = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=chat_messages,
        max_tokens=2048,
    )
    choice = out.choices[0].message.content
    return (choice or "").strip()


def _generate_anthropic(
    system: str,
    api_messages: list[dict],
) -> str:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (required when LLM_PROVIDER=anthropic)")
    client = Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=system,
        messages=api_messages,
    )
    parts = []
    for block in msg.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def generate_answer(
    *,
    paper_title: str,
    arxiv_id: str,
    abstract: str,
    context_chunks: list[tuple[int, str]],
    messages: list[dict],
) -> str:
    system = build_system_prompt(
        paper_title=paper_title,
        arxiv_id=arxiv_id,
        abstract=abstract,
        context_chunks=context_chunks,
    )
    api_messages = _normalize_messages(messages)
    provider = settings.llm_provider.lower().strip()
    if provider == "openrouter":
        return _generate_openrouter(system, api_messages)
    if provider == "anthropic":
        return _generate_anthropic(system, api_messages)
    raise RuntimeError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r} (use openrouter or anthropic)")

"""RAG tool: full-text search over the indexed arXiv paper."""
from __future__ import annotations

import sqlite3

from app.rag.pipeline import ensure_paper_indexed, retrieve_hybrid

SCHEMA = {
    "name": "rag_search",
    "description": (
        "Search the full text of the current arXiv paper for passages relevant to a query. "
        "Returns the most relevant excerpts with chunk IDs for citation. "
        "Use this tool whenever the user asks about the paper's methodology, equations, "
        "experimental setup, results, or any content from the paper itself."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A focused natural-language search query about the paper.",
            }
        },
        "required": ["query"],
    },
}


async def rag_search(
    conn: sqlite3.Connection,
    arxiv_id: str,
    query: str,
) -> str:
    await ensure_paper_indexed(conn, arxiv_id)
    chunks = retrieve_hybrid(conn, arxiv_id, query)
    if not chunks:
        return "No relevant passages found for this query."
    parts = [f"[chunk_id={cid}]\n{text}" for cid, text in chunks]
    return "\n\n---\n\n".join(parts)

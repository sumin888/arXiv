"""arXiv search tool via the public arXiv Atom API."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

_NS = {"atom": "http://www.w3.org/2005/Atom"}

SCHEMA = {
    "name": "search_arxiv",
    "description": (
        "Search arXiv for papers related to a topic, method, or author. "
        "Returns titles, authors, arXiv IDs, and abstracts. "
        "Useful for finding related work, prior art, or follow-up papers."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search terms (keywords, method names, author names, etc.)",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of papers to return (default 5, max 10)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}


async def search_arxiv(query: str, max_results: int = 5) -> str:
    max_results = min(int(max_results), 10)
    params = {
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get("https://export.arxiv.org/api/query", params=params)
        r.raise_for_status()

    root = ET.fromstring(r.text)
    entries = root.findall("atom:entry", _NS)
    if not entries:
        return "No arXiv results found."

    results = []
    for entry in entries:
        aid = (entry.findtext("atom:id", "", _NS) or "").split("/abs/")[-1].strip()
        title = (entry.findtext("atom:title", "", _NS) or "").strip()
        summary = (entry.findtext("atom:summary", "", _NS) or "").strip()[:300]
        authors = [
            (a.findtext("atom:name", "", _NS) or "").strip()
            for a in entry.findall("atom:author", _NS)
        ][:3]
        results.append(
            f"[{aid}] {title}\n"
            f"Authors: {', '.join(authors)}\n"
            f"Abstract: {summary}…"
        )

    return "\n\n".join(results)

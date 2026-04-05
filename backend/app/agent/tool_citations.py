"""Citation tool via the Semantic Scholar Graph API."""
from __future__ import annotations

import httpx

SCHEMA = {
    "name": "fetch_citations",
    "description": (
        "Fetch citation data for an arXiv paper from Semantic Scholar: "
        "total citation count, its references, and papers that cite it."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "arxiv_id": {
                "type": "string",
                "description": "arXiv paper ID (e.g. '2301.07041')",
            },
            "limit": {
                "type": "integer",
                "description": "Max references/citations to list (default 10)",
                "default": 10,
            },
        },
        "required": ["arxiv_id"],
    },
}


async def fetch_citations(arxiv_id: str, limit: int = 10) -> str:
    limit = min(int(limit), 50)
    url = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}"
    params = {
        "fields": "title,authors,year,citationCount,references.title,citations.title"
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params)
        if r.status_code == 404:
            return f"Paper arXiv:{arxiv_id} not found in Semantic Scholar."
        r.raise_for_status()
        data = r.json()

    parts = [
        f"Title: {data.get('title', 'N/A')}",
        f"Total citations: {data.get('citationCount', 0)}",
    ]

    refs = data.get("references", [])[:limit]
    if refs:
        parts.append(f"\nReferences ({len(refs)} shown):")
        for ref in refs:
            parts.append(f"  · {ref.get('title', 'Unknown')}")

    cits = data.get("citations", [])[:limit]
    if cits:
        parts.append(f"\nCited by ({len(cits)} shown):")
        for cit in cits:
            parts.append(f"  · {cit.get('title', 'Unknown')}")

    return "\n".join(parts)

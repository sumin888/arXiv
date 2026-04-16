"""Cross-domain bridge paper sampler — surfaces methodologically connected papers from other fields."""
from __future__ import annotations

import random
import xml.etree.ElementTree as ET

import httpx

_NS = {"atom": "http://www.w3.org/2005/Atom"}

# Maps current paper's primary category → candidate bridge categories from other domains
_BRIDGE_MAP: dict[str, list[str]] = {
    "cs.LG":    ["cs.CE", "q-bio.NC", "econ.EM", "physics.data-an", "stat.AP"],
    "cs.CV":    ["q-bio.QM", "astro-ph.IM", "physics.med-ph", "cs.CE", "econ.GN"],
    "cs.CL":    ["q-bio.GN", "econ.GN", "physics.soc-ph", "cs.CE", "stat.AP"],
    "cs.NLP":   ["q-bio.GN", "econ.GN", "physics.soc-ph", "cs.CE"],
    "cs.AI":    ["q-bio.NC", "econ.EM", "cs.CE", "physics.soc-ph"],
    "cs.RO":    ["q-bio.NC", "cs.CE", "physics.flu-dyn", "econ.EM"],
    "stat.ML":  ["q-bio.QM", "econ.EM", "physics.data-an", "astro-ph.IM"],
    "math.OC":  ["q-bio.NC", "econ.EM", "cs.CE", "physics.flu-dyn"],
    "physics.comp-ph": ["cs.CE", "q-bio.QM", "econ.EM", "astro-ph.IM"],
    "q-bio.NC": ["cs.LG", "cs.NE", "econ.EM", "physics.soc-ph"],
    "econ.EM":  ["cs.LG", "stat.ML", "physics.data-an", "q-bio.PE"],
}
_DEFAULT_BRIDGES = ["cs.CE", "q-bio.NC", "econ.EM", "physics.data-an", "astro-ph.IM"]

SCHEMA = {
    "name": "sample_bridge_paper",
    "description": (
        "Find a paper from a different academic domain that uses the same core methods "
        "as the current paper, revealing cross-disciplinary connections. "
        "Call this proactively every 3 user messages to surface conceptual drift opportunities."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "method_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Key methods or techniques from the current paper "
                    "(e.g. ['attention mechanism', 'contrastive learning', 'Bayesian inference']). "
                    "Extract these from the abstract and your RAG results."
                ),
            },
            "current_category": {
                "type": "string",
                "description": (
                    "Primary arXiv subject category of the current paper (e.g. 'cs.LG'). "
                    "Used to choose a bridge from a different domain."
                ),
            },
        },
        "required": ["method_keywords"],
    },
}


async def sample_bridge_paper(
    method_keywords: list[str],
    current_category: str = "",
) -> str:
    if not method_keywords:
        return "No method keywords provided — cannot find a bridge paper."

    # Pick a bridge category from a different domain
    bridge_options = _BRIDGE_MAP.get(current_category, _DEFAULT_BRIDGES)
    bridge_cat = random.choice(bridge_options)

    # Build arXiv query: keywords + category filter
    kw_str = " ".join(
        f'"{kw}"' if " " in kw else kw for kw in method_keywords[:3]
    )
    search_query = f"cat:{bridge_cat} AND all:{kw_str}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            "https://export.arxiv.org/api/query",
            params={"search_query": search_query, "max_results": 5, "sortBy": "relevance"},
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
        entries = root.findall("atom:entry", _NS)

        # Fallback: drop category filter if no results
        if not entries:
            r = await client.get(
                "https://export.arxiv.org/api/query",
                params={"search_query": f"all:{kw_str}", "max_results": 5, "sortBy": "relevance"},
            )
            r.raise_for_status()
            root = ET.fromstring(r.text)
            entries = root.findall("atom:entry", _NS)

    if not entries:
        return "No bridge paper candidates found for these method keywords."

    # Parse top 3 candidates
    candidates = []
    for entry in entries[:3]:
        aid = (entry.findtext("atom:id", "", _NS) or "").split("/abs/")[-1].strip()
        title = (entry.findtext("atom:title", "", _NS) or "").replace("\n", " ").strip()
        abstract = (entry.findtext("atom:summary", "", _NS) or "").replace("\n", " ").strip()[:400]
        cat_el = entry.find("atom:category", _NS)
        domain = (cat_el.get("term", "") if cat_el is not None else "") or bridge_cat
        if aid and title:
            candidates.append({"arxiv_id": aid, "title": title, "abstract": abstract, "domain": domain})

    if not candidates:
        return "Could not parse bridge paper candidates."

    # Sample one, weighted toward more relevant (higher-ranked) results
    weights = [3, 2, 1][: len(candidates)]
    chosen = random.choices(candidates, weights=weights, k=1)[0]

    # Generate bridge_reason from shared method keywords
    shared = " and ".join(method_keywords[:2])
    bridge_reason = (
        f"Both papers apply {shared} — the current paper in "
        f"{current_category or 'its domain'}, while this one uses the same approach "
        f"in {chosen['domain']}."
    )

    return (
        f"title: {chosen['title']}\n"
        f"arxiv_id: {chosen['arxiv_id']}\n"
        f"domain: {chosen['domain']}\n"
        f"bridge_reason: {bridge_reason}\n"
        f"abstract: {chosen['abstract']}"
    )

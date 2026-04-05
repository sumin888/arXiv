"""GitHub repo fetcher tool via GitHub REST API."""
from __future__ import annotations

import base64

import httpx

from app.config import settings

SCHEMA = {
    "name": "fetch_github_repo",
    "description": (
        "Fetch metadata, README, and directory listing for a GitHub repository. "
        "Useful for exploring official code implementations of arXiv papers, "
        "understanding repo structure, and finding experiment entry points."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository in 'owner/name' format (e.g. 'huggingface/transformers')",
            }
        },
        "required": ["repo"],
    },
}


async def fetch_github_repo(repo: str) -> str:
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        r = await client.get(f"https://api.github.com/repos/{repo}")
        if r.status_code == 404:
            return f"GitHub repo '{repo}' not found."
        r.raise_for_status()
        meta = r.json()

        # Top-level directory listing
        tree_items: list[str] = []
        tr = await client.get(f"https://api.github.com/repos/{repo}/git/trees/HEAD")
        if tr.ok:
            tree_items = [
                f"  {'📁' if item['type'] == 'tree' else '📄'} {item['path']}"
                for item in tr.json().get("tree", [])[:30]
            ]

        # README (first 1500 chars)
        readme_text = ""
        rr = await client.get(f"https://api.github.com/repos/{repo}/readme")
        if rr.ok:
            raw = base64.b64decode(rr.json().get("content", "")).decode("utf-8", errors="replace")
            readme_text = raw[:1500]

    parts = [
        f"Repo: {meta.get('full_name')}",
        f"Description: {meta.get('description') or 'N/A'}",
        f"Stars: {meta.get('stargazers_count', 0)} | Forks: {meta.get('forks_count', 0)}",
        f"Language: {meta.get('language') or 'N/A'}",
        f"Topics: {', '.join(meta.get('topics', [])) or 'none'}",
    ]
    if tree_items:
        parts.append("\nTop-level files/dirs:\n" + "\n".join(tree_items))
    if readme_text:
        parts.append(f"\nREADME (first 1500 chars):\n{readme_text}")

    return "\n".join(parts)

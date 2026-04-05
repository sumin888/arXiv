from io import BytesIO

import httpx
from pypdf import PdfReader


def arxiv_pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


async def fetch_pdf_bytes(arxiv_id: str, timeout: float = 120.0) -> bytes:
    url = arxiv_pdf_url(arxiv_id)
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        r = await client.get(url, headers={"User-Agent": "arXiv-Agent-RAG/1.0"})
        r.raise_for_status()
        return r.content


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        parts.append(t)
    return "\n\n".join(parts).strip()

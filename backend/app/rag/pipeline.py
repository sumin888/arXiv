from __future__ import annotations

import sqlite3
import threading

from app.config import settings
from app.rag import chunk as chunk_mod
from app.rag import embed as embed_mod
from app.rag import pdf as pdf_mod
from app.rag.llm import generate_answer
from app.rag.hybrid import reciprocal_rank_fusion
from app.rag.store import (
    connect,
    fetch_chunk_texts,
    fts5_match_query,
    init_schema,
    insert_paper_chunks,
    is_paper_indexed,
    search_fts,
    search_vector,
)

_db_lock = threading.Lock()


def get_connection() -> sqlite3.Connection:
    conn = connect(settings.db_path)
    init_schema(conn)
    return conn


async def ensure_paper_indexed(conn: sqlite3.Connection, arxiv_id: str) -> None:
    with _db_lock:
        if is_paper_indexed(conn, arxiv_id):
            return
    raw = await pdf_mod.fetch_pdf_bytes(arxiv_id)
    text = pdf_mod.extract_text_from_pdf(raw)
    if not text or len(text) < 200:
        raise ValueError(
            "Could not extract enough text from the PDF (arXiv PDFs vary in quality)."
        )
    chunks = chunk_mod.chunk_text(text)
    if not chunks:
        raise ValueError("Chunking produced no segments.")
    embeddings = embed_mod.embed_texts(chunks)
    with _db_lock:
        if is_paper_indexed(conn, arxiv_id):
            return
        insert_paper_chunks(conn, arxiv_id, chunks, embeddings)


def retrieve_hybrid(
    conn: sqlite3.Connection,
    arxiv_id: str,
    user_query: str,
) -> list[tuple[int, str]]:
    q_emb = embed_mod.embed_query(user_query)
    q_json = embed_mod.embedding_to_json(q_emb)
    fts_q = fts5_match_query(user_query)
    with _db_lock:
        vec_rows = search_vector(conn, arxiv_id, q_json)
        fts_rows: list[tuple[int, float]] = []
        if fts_q:
            fts_rows = search_fts(conn, arxiv_id, fts_q)

    vec_ids = [cid for cid, _ in vec_rows]
    fts_ids = [cid for cid, _ in fts_rows]
    fused = reciprocal_rank_fusion(vec_ids, fts_ids)
    top_ids = [cid for cid, _ in fused[: settings.context_chunks]]
    with _db_lock:
        texts = fetch_chunk_texts(conn, top_ids)
    ordered = [(cid, texts[cid]) for cid in top_ids if cid in texts]
    return ordered


async def answer_query(
    conn: sqlite3.Connection,
    *,
    arxiv_id: str,
    paper_title: str,
    abstract: str,
    messages: list[dict],
) -> str:
    await ensure_paper_indexed(conn, arxiv_id)
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user" and (m.get("content") or "").strip():
            last_user = m["content"].strip()
            break
    if not last_user:
        raise ValueError("No user message found")
    context = retrieve_hybrid(conn, arxiv_id, last_user)
    if not context:
        raise RuntimeError("Retrieval returned no chunks for this query.")
    return generate_answer(
        paper_title=paper_title,
        arxiv_id=arxiv_id,
        abstract=abstract,
        context_chunks=context,
        messages=messages,
    )

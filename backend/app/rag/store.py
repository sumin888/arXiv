from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import sqlite_vec

from app.config import settings


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS papers (
            arxiv_id TEXT PRIMARY KEY,
            indexed_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arxiv_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            UNIQUE(arxiv_id, chunk_index)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vectors USING vec0(
            chunk_id INTEGER PRIMARY KEY,
            arxiv_id TEXT PARTITION KEY,
            embedding float[384] distance_metric=cosine
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            text,
            tokenize='porter'
        );
        """
    )
    conn.commit()


def is_paper_indexed(conn: sqlite3.Connection, arxiv_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM papers WHERE arxiv_id = ? LIMIT 1", (arxiv_id,)
    ).fetchone()
    return row is not None


def delete_paper(conn: sqlite3.Connection, arxiv_id: str) -> None:
    rows = conn.execute(
        "SELECT id FROM chunks WHERE arxiv_id = ?", (arxiv_id,)
    ).fetchall()
    ids = [r["id"] for r in rows]
    if ids:
        qmarks = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM chunk_vectors WHERE chunk_id IN ({qmarks})", ids)
        conn.execute(f"DELETE FROM chunks_fts WHERE rowid IN ({qmarks})", ids)
    conn.execute("DELETE FROM chunks WHERE arxiv_id = ?", (arxiv_id,))
    conn.execute("DELETE FROM papers WHERE arxiv_id = ?", (arxiv_id,))
    conn.commit()


def insert_paper_chunks(
    conn: sqlite3.Connection,
    arxiv_id: str,
    chunk_texts: list[str],
    embeddings: list[list[float]],
) -> None:
    if len(chunk_texts) != len(embeddings):
        raise ValueError("chunks and embeddings length mismatch")
    delete_paper(conn, arxiv_id)
    for i, (text, emb) in enumerate(zip(chunk_texts, embeddings)):
        cur = conn.execute(
            "INSERT INTO chunks(arxiv_id, chunk_index, text) VALUES (?, ?, ?)",
            (arxiv_id, i, text),
        )
        chunk_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO chunk_vectors(chunk_id, arxiv_id, embedding) VALUES (?, ?, ?)",
            (chunk_id, arxiv_id, json.dumps(emb)),
        )
        conn.execute(
            "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)", (chunk_id, text)
        )
    conn.execute(
        "INSERT INTO papers(arxiv_id) VALUES (?) ON CONFLICT(arxiv_id) DO UPDATE SET indexed_at = datetime('now')",
        (arxiv_id,),
    )
    conn.commit()


def fts5_match_query(user_query: str, max_terms: int = 14) -> str | None:
    words = re.findall(r"[a-zA-Z0-9]+", user_query.lower())
    if not words:
        return None
    words = words[:max_terms]
    return " AND ".join(f'"{w}"' for w in words)


def search_vector(
    conn: sqlite3.Connection,
    arxiv_id: str,
    query_embedding_json: str,
    k: int | None = None,
) -> list[tuple[int, float]]:
    k = k if k is not None else settings.vector_top_k
    rows = conn.execute(
        """
        SELECT chunk_id, distance
        FROM chunk_vectors
        WHERE embedding MATCH ?
          AND k = ?
          AND arxiv_id = ?
        """,
        (query_embedding_json, k, arxiv_id),
    ).fetchall()
    return [(int(r["chunk_id"]), float(r["distance"])) for r in rows]


def search_fts(
    conn: sqlite3.Connection,
    arxiv_id: str,
    fts_query: str,
    k: int | None = None,
) -> list[tuple[int, float]]:
    k = k if k is not None else settings.fts_top_k
    rows = conn.execute(
        """
        SELECT c.id AS chunk_id, bm25(chunks_fts) AS bm
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        WHERE chunks_fts MATCH ?
          AND c.arxiv_id = ?
        ORDER BY bm ASC
        LIMIT ?
        """,
        (fts_query, arxiv_id, k),
    ).fetchall()
    return [(int(r["chunk_id"]), float(r["bm"])) for r in rows]


def fetch_chunk_texts(conn: sqlite3.Connection, chunk_ids: list[int]) -> dict[int, str]:
    if not chunk_ids:
        return {}
    qmarks = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"SELECT id, text FROM chunks WHERE id IN ({qmarks})", chunk_ids
    ).fetchall()
    return {int(r["id"]): r["text"] for r in rows}

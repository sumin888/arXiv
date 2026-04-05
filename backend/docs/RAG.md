# Hybrid RAG design (sqlite-vec + FTS5)

## Running the API

From the `backend/` directory (with a virtualenv that has `requirements.txt` installed):

```bash
cp .env.example .env   # add OPENROUTER_API_KEY (or switch to Anthropic — see .env.example)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: `GET http://127.0.0.1:8000/health` (includes `llm_provider` and `llm_model`)  
Query: `POST http://127.0.0.1:8000/api/query` with JSON body `{ "arxivId", "title", "abstract", "messages" }`.

**Structured request validation** is defined in `app/schemas.py` (Pydantic `BaseModel`s): `messages[].role` must be `user` or `assistant`, and the last non-empty message must be from the `user`.

---

This backend answers questions about a single arXiv paper by retrieving relevant **chunks** of extracted PDF text, then asking an **LLM** (default: **OpenRouter** with a free NVIDIA model) to respond using only those excerpts (plus metadata you send from the extension).

Retrieval is **hybrid**: dense vectors and lexical (BM25) search run in parallel, then results are fused with **Reciprocal Rank Fusion (RRF)** so we do not have to put incomparable scores on a common scale.

---

## End-to-end flow

1. **Index (once per `arxiv_id`)**  
   - Download `https://arxiv.org/pdf/{arxiv_id}.pdf`.  
   - Extract text with **PyPDF** (quality varies by PDF).  
   - Split into overlapping character windows (**chunking**).  
   - Embed each chunk with **Sentence-Transformers** `all-MiniLM-L6-v2` → **384-dimensional** L2-normalized vectors.  
   - Persist rows in SQLite: canonical `chunks` table, **sqlite-vec `vec0`** for vectors, **FTS5** for full text.

2. **Query (each user message)**  
   - Embed the **latest user message** with the same model.  
   - **Vector branch:** KNN on `vec0` restricted by `arxiv_id` **partition key** (fast per-paper search).  
   - **Lexical branch:** FTS5 `MATCH` with **Porter stemming**, `bm25()` ranking, filtered by joining to `chunks.arxiv_id`.  
   - **Fuse** the two ranked lists with RRF, take the top **N** chunk IDs, load their text, and pass them to the LLM with a strict “grounded in excerpts” system prompt.

---

## Storage layout (SQLite)

| Artifact | Role |
|----------|------|
| `papers` | Marks which `arxiv_id` values are fully indexed. |
| `chunks` | `id`, `arxiv_id`, `chunk_index`, `text` — source of truth for chunk text. |
| `chunk_vectors` (`vec0`) | One row per chunk: `chunk_id` (PK), `arxiv_id` **partition key**, `embedding float[384]`. |
| `chunks_fts` (FTS5) | `rowid` = `chunks.id`, indexed column `text`, `tokenize='porter'`. |

Inserts are transactional: for a re-index we delete prior rows for that `arxiv_id` in all three structures, then reinsert.

---

## 1) sqlite-vec (`vec0`) — vector / semantic search

### What it stores

- **384 floats per chunk**, matching `sentence-transformers/all-MiniLM-L6-v2`.  
- Vectors are stored in a **`vec0` virtual table**, which keeps a compact on-disk representation and uses an **approximate nearest neighbor (ANN)** path for `MATCH` KNN queries (see [sqlite-vec](https://github.com/asg017/sqlite-vec) — the project is pre-1.0; behavior may evolve).

### Distance metric: **cosine**

The embedding column is declared with:

```sql
embedding float[384] distance_metric=cosine
```

So the `distance` returned on KNN queries is **cosine distance** in the sense of sqlite-vec’s `vec_distance_cosine()`:

- **0** → identical direction (same orientation in vector space; strongest semantic match).  
- **2** → opposite direction (weakest / “opposite” alignment in that cosine distance definition).

This matches the usual mental model: **lower distance = closer / more similar** for retrieval ordering.

### Query shape

We constrain the ANN search to one paper using a **`arxiv_id TEXT PARTITION KEY`** on the `vec0` table so sqlite-vec can shard internally and avoid scanning unrelated papers:

```sql
SELECT chunk_id, distance
FROM chunk_vectors
WHERE embedding MATCH :query_json
  AND k = :vector_top_k
  AND arxiv_id = :arxiv_id;
```

`:query_json` is a JSON array of 384 floats for the **query embedding** (same format as inserts).

---

## 2) FTS5 — BM25 keyword search

### What it indexes

- The same chunk `text` as in `chunks`, duplicated into **`chunks_fts`** with `rowid` aligned to `chunks.id`.  
- **Tokenizer:** `porter` (Porter stemmer) so inflected forms like `running` / `runs` tend to match the same stem.

### Query construction

User text is tokenized to alphanumeric “words” (lowercased), capped to a small maximum count, and joined with **AND** so hits prefer chunks that contain **more of the query terms**:

```text
"attention" AND "mechanism" AND "layer"
```

If the query yields **no** tokens (e.g. only punctuation), we **skip** the FTS branch and rely on vectors only.

### Scoring: `bm25(chunks_fts)`

We order lexical hits with SQLite’s FTS5 auxiliary function **`bm25(chunks_fts)`**.

- BM25 ranks documents by term frequency / document frequency (classic lexical relevance).  
- In our usage, **smaller `bm25` values indicate a better lexical match** (we `ORDER BY bm ASC`).  
- Values are often **negative**; that is normal for this API — **do not compare raw BM25 scores to vector distance**. Only **rank positions** matter for the hybrid step.

We restrict matches to the current paper by joining `chunks_fts.rowid` to `chunks.id` and filtering `chunks.arxiv_id`.

---

## 3) Hybrid fusion — Reciprocal Rank Fusion (RRF)

Vector cosine distance and BM25 scores are **not calibrated** to each other. Instead of normalizing scores, we use **RRF** over the **ranked ID lists**:

For each chunk ID \(d\),

\[
\text{RRF}(d) = \sum_{i \in \{\text{vec}, \text{fts}\}} \frac{1}{k + \text{rank}_i(d)}
\]

- \(\text{rank}_i(d)\) is the 1-based rank of \(d\) in branch \(i\), if present; if absent, that branch contributes nothing.  
- **`k`** (default **60**, configurable via `RRF_K`) is the usual RRF constant; larger \(k\) dampens the influence of top ranks.

We sort by **descending RRF score**, break ties by chunk ID, and take the top **`CONTEXT_CHUNKS`** (default **10**) for the LLM context.

---

## 4) Generation (OpenRouter or Anthropic)

Retrieved chunks are formatted as labeled blocks (`[chunk_id=…]`) in the system prompt. The model is instructed to stay within that evidence and to cite `chunk_id` when making specific claims.

**OpenRouter (default):** set **`OPENROUTER_API_KEY`** in `backend/.env` (create the key at [openrouter.ai/keys](https://openrouter.ai/keys)). The default model is **`OPENROUTER_MODEL=nvidia/nemotron-nano-9b-v2:free`**; change it to any id from [openrouter.ai/models](https://openrouter.ai/models) (e.g. another `:free` NVIDIA model). Optional: **`OPENROUTER_HTTP_REFERER`** for OpenRouter’s recommended referer header.

**Anthropic:** set **`LLM_PROVIDER=anthropic`**, **`ANTHROPIC_API_KEY`**, and optionally **`ANTHROPIC_MODEL`**.

---

## 5) Operational notes

- **Concurrency:** SQLite access for reads/writes is guarded with a lock around DB sections; embedding runs outside the lock where possible.  
- **WAL:** `PRAGMA journal_mode=WAL` improves concurrent read behavior.  
- **PDFs:** Some arXiv PDFs extract poorly; we fail fast if extracted text is too short.  
- **Caching:** Indexed papers are reused from disk until you delete the DB or we add an explicit eviction API.

---

## Configuration reference (environment)

| Variable | Meaning |
|----------|---------|
| `LLM_PROVIDER` | `openrouter` (default) or `anthropic` |
| `OPENROUTER_API_KEY` | OpenRouter API key ([keys](https://openrouter.ai/keys)) |
| `OPENROUTER_MODEL` | OpenRouter model id (default free NVIDIA nano) |
| `OPENROUTER_HTTP_REFERER` | Optional referer URL for OpenRouter |
| `ANTHROPIC_API_KEY` | Direct Anthropic API key (if `LLM_PROVIDER=anthropic`) |
| `ANTHROPIC_MODEL` | Anthropic model id |
| `EMBEDDING_MODEL` | Sentence-Transformers model name (must stay **384-dim** for this schema) |
| `DATA_DIR` / `SQLITE_PATH` | Where the SQLite file lives (`arxiv_rag.db` by default under `DATA_DIR`) |
| `VECTOR_TOP_K` / `FTS_TOP_K` | How many hits each branch contributes to RRF |
| `CONTEXT_CHUNKS` | How many fused chunks go to the LLM |
| `RRF_K` | RRF constant \(k\) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Character-based chunking |

See `backend/.env.example`.

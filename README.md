# PaperAgent — arXiv AI Research Assistant

A Chrome browser extension that attaches an expert AI agent to any **arxiv.org** abstract page. The agent is grounded in the paper's full text via hybrid RAG and can search related work, fetch GitHub implementations, run experiment code, and surface cross-domain connections.

---

## Features

- **Per-paper RAG** — PDF downloaded and indexed on first visit; hybrid vector + full-text search (SQLite-vec + FTS5 with Reciprocal Rank Fusion)
- **Tool-calling agent loop** — model autonomously decides when to call tools: `rag_search`, `search_arxiv`, `fetch_citations`, `fetch_github_repo`, `run_experiment`, `execute_python`, `compare_results`
- **Bridge paper discovery** — every few turns the agent surfaces a paper from a *different domain* that uses the same core method, with a one-click deep-dive mode
- **Dual LLM provider** — works with Anthropic (Claude) or any OpenRouter model; swap via a single env var
- **Browser extension** — Chrome side panel (Manifest V3); activates automatically on `arxiv.org/abs/*` pages

---

## Architecture

```
arxiv.org page
     │  (arXiv ID, title, authors, abstract)
     ▼
[Chrome Extension — content.js]
     │
     ▼
[Side Panel — React + Vite]
     │  POST /chat  { arxivId, messages, … }
     ▼
[FastAPI Backend — Python]
  ├── RAG pipeline
  │     PDF → chunk (1200 chars / 180 overlap)
  │         → embed (all-MiniLM-L6-v2)
  │         → SQLite-vec + FTS5
  │         → Hybrid retrieval (RRF)
  └── Agent loop
        pre-fetch context → system prompt
        → LLM (Anthropic / OpenRouter)
        → tool calls → tool results → …
        → final reply  (+optional <bridge> tag)
```

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ (for building the sidebar)
- Chrome or Chromium browser
- An API key: [OpenRouter](https://openrouter.ai) (free tier available) or [Anthropic](https://console.anthropic.com)

### 1. Backend

```bash
cd backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create your .env file
cat > .env << 'EOF'
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_MODEL=nvidia/nemotron-nano-9b-v2:free
EOF

# Start the server
uvicorn app.main:app --reload
# → running at http://127.0.0.1:8000
```

To use Anthropic instead:
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### 2. Extension

**Option A — use the pre-built sidebar (no Node.js needed)**

The `sidebar/` folder contains a production build. Skip to step 3.

**Option B — build from source**

```bash
cd sidebar-src
npm install
npm run build
# output goes to ../sidebar/
```

### 3. Load in Chrome

1. Open `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked** → select the repo root folder
4. Navigate to any `arxiv.org/abs/` page
5. Click the extension icon → side panel opens

---

## Usage

1. Open any arXiv abstract page, e.g. `https://arxiv.org/abs/1706.03762`
2. The agent greets you and begins indexing the PDF in the background
3. Ask anything about the paper — methodology, results, related work, code
4. After a few turns, a **bridge paper** suggestion may appear — click "Explore" for a cross-domain comparison
5. Use the **Runs** tab to ask the agent to clone and execute the paper's official code

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openrouter` | `openrouter` or `anthropic` |
| `OPENROUTER_API_KEY` | — | Required if provider is `openrouter` |
| `OPENROUTER_MODEL` | `nvidia/nemotron-nano-9b-v2:free` | Any OpenRouter model slug |
| `ANTHROPIC_API_KEY` | — | Required if provider is `anthropic` |
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet-20241022` | Anthropic model ID |
| `CHUNK_SIZE` | `1200` | PDF chunk size in characters |
| `CHUNK_OVERLAP` | `180` | Overlap between consecutive chunks |
| `CONTEXT_CHUNKS` | `10` | Top-k chunks injected into the prompt |
| `E2B_API_KEY` | — | Optional — enables sandboxed code execution |
| `GITHUB_TOKEN` | — | Optional — higher GitHub API rate limits |

---

## Limitations

- The backend must be running locally; there is no hosted version
- Free-tier OpenRouter models rate-limit under concurrent load (see [HW8 experiments](experiments/HW8_summary.md))
- Code execution (`run_experiment`) clones and runs arbitrary code — review repos before running
- PDFs with image-only content (scanned papers) produce little or no extractable text
- Bridge paper discovery requires the arXiv search API to be reachable

---

## Project Structure

```
├── manifest.json          # Chrome extension manifest (MV3)
├── background/            # Service worker — opens side panel, relays paper metadata
├── content/               # Content script — extracts paper info from arxiv.org DOM
├── sidebar/               # Pre-built extension UI (React + Vite output)
├── sidebar-src/           # UI source (TypeScript, React, Tailwind, shadcn/ui)
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI app — /index, /chat, /api/query, /health
│   │   ├── agent/         # Tool-calling agent loop + tool implementations
│   │   ├── rag/           # PDF fetch, chunking, embedding, hybrid retrieval
│   │   ├── schemas.py     # Pydantic request/response models
│   │   └── config.py      # Settings (pydantic-settings, .env)
│   └── requirements.txt
└── experiments/           # HW8 scaled experiment runner + results
```

---

## License

MIT

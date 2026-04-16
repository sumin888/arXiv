from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.rag import pipeline
from app.agent.loop import run_agent
from app.schemas import ChatRequest, IndexRequest, QueryRequest, QueryResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.rag.embed import get_model

    get_model()
    app.state.db = pipeline.get_connection()
    yield
    conn = getattr(app.state, "db", None)
    if conn is not None:
        conn.close()


app = FastAPI(title="arXiv RAG API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    model = (
        settings.openrouter_model
        if settings.llm_provider == "openrouter"
        else settings.anthropic_model
    )
    return {
        "ok": True,
        "db": str(settings.db_path),
        "llm_provider": settings.llm_provider,
        "llm_model": model,
    }


@app.post("/index")
async def index_paper(req: IndexRequest, background_tasks: BackgroundTasks):
    """Trigger PDF download + embedding in the background so the first /chat is instant."""
    conn = app.state.db
    background_tasks.add_task(pipeline.ensure_paper_indexed, conn, req.arxiv_id.strip())
    return {"status": "indexing", "arxivId": req.arxiv_id}


@app.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    conn = app.state.db
    msgs = [m.model_dump() for m in req.messages]
    try:
        reply = await pipeline.answer_query(
            conn,
            arxiv_id=req.arxiv_id.strip(),
            paper_title=req.title.strip(),
            abstract=req.abstract.strip(),
            messages=msgs,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return QueryResponse(reply=reply)


@app.post("/chat", response_model=QueryResponse)
async def chat(req: ChatRequest):
    conn = app.state.db
    msgs = [m.model_dump() for m in req.messages]
    try:
        reply = await run_agent(
            conn=conn,
            arxiv_id=req.arxiv_id.strip(),
            paper_title=req.title.strip(),
            abstract=req.abstract.strip(),
            messages=msgs,
            message_count=req.message_count,
            primary_category=req.primary_category.strip(),
            active_bridge_id=req.active_bridge_id.strip(),
            active_bridge_title=req.active_bridge_title.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return QueryResponse(reply=reply)

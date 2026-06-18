from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from pipeline.entity_extractor import EntityExtractor
from retrieval.vector_retriever import VectorRetriever
from api.routes.chat import router as chat_router
from api.routes.cv import router as cv_router

load_dotenv()

_GRAPH_HTML = Path("graph_viz.html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.retriever = VectorRetriever()
    app.state.extractor = EntityExtractor()
    yield
    app.state.retriever.close()


app = FastAPI(title="Immigration RAG Chatbot", version="0.1.0", lifespan=lifespan)
app.include_router(chat_router)
app.include_router(cv_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/graph", response_class=HTMLResponse)
def graph() -> HTMLResponse:
    if not _GRAPH_HTML.exists():
        return HTMLResponse("<h2>graph_viz.html not found. Run: python -m graph.visualize</h2>", status_code=404)
    return HTMLResponse(_GRAPH_HTML.read_text(encoding="utf-8"))

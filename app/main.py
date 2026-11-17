from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from app.config import settings
from app.database import engine, Base

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting AI Interviewer Platform...")

    # Create all DB tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables ready")
    except Exception as e:
        logger.warning(f"⚠️ DB init skipped (will retry on request): {e}")

    # Initialize MinIO bucket (skip if unavailable)
    try:
        from app.utils.file_storage import storage
        await storage.ensure_bucket()
        logger.info("✅ MinIO storage ready")
    except Exception as e:
        logger.warning(f"⚠️ MinIO not available (file uploads disabled): {e}")

    # Initialize ChromaDB
    try:
        from app.vector_store.chroma_client import chroma_client
        counts = chroma_client.get_collection_counts()
        logger.info(f"✅ ChromaDB ready — collections: {counts}")
    except Exception as e:
        logger.warning(f"⚠️ ChromaDB init issue: {e}")

    logger.info("✅ AI Interviewer Platform is live on http://localhost:8001/docs")
    yield

    logger.info("🛑 Shutting down...")
    await engine.dispose()


app = FastAPI(
    title="AI Interviewer Platform",
    description="""
## 🤖 AI Interviewer Platform

Voice-powered mock interview system with:
- **Resume Parsing** (PDF/DOCX → structured data → ChromaDB)
- **RAG Question Generation** (LLM generates fresh, unique questions every session)
- **Voice Interview Loop** (WebSocket: TTS questions → Whisper STT → LLM scoring)
- **Adaptive Follow-ups** (auto-generated when score < 6/10)
- **PDF Scorecards** (emailed + downloadable)
- **Dashboard** (session history, score analytics)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Import and register all routers ─────────────────────────────────────────
from app.routers import auth, resume, interview, voice, scoring, scorecard, dashboard

app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(interview.router)
app.include_router(voice.router)
app.include_router(scoring.router)
app.include_router(scorecard.router)
app.include_router(dashboard.router)


# ─── Serve React Frontend ────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/app", tags=["Frontend"], include_in_schema=False)
async def serve_frontend():
    """Serve the React frontend SPA."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"error": "Frontend not found"}


@app.get("/health", tags=["Health"])
async def health_check():
    """Check service health and availability of dependencies."""
    status = {"status": "healthy", "version": "1.0.0", "llm_provider": settings.LLM_PROVIDER}

    # Check DB
    try:
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await db.execute(__import__("sqlalchemy").text("SELECT 1"))
        status["database"] = "✅ connected"
    except Exception as e:
        status["database"] = f"❌ {str(e)[:60]}"

    # Check ChromaDB
    try:
        from app.vector_store.chroma_client import chroma_client
        counts = chroma_client.get_collection_counts()
        status["chromadb"] = f"✅ {counts}"
    except Exception as e:
        status["chromadb"] = f"❌ {str(e)[:60]}"

    # Check MinIO
    try:
        from app.utils.file_storage import storage
        storage.client.list_buckets()
        status["minio"] = "✅ connected"
    except Exception as e:
        status["minio"] = f"❌ {str(e)[:60]}"

    return status


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "🤖 AI Interviewer Platform API",
        "docs": "http://localhost:8001/docs",
        "redoc": "http://localhost:8001/redoc",
        "health": "http://localhost:8001/health",
    }

"""
TennisModel KCR — FastAPI application entry point.
Run locally:   uvicorn main:app --reload
Deploy:        See Dockerfile / railway.toml / render.yaml
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import auth, predictions, rankings, players
from backend.services.config import settings

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── App ───────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("TennisModel KCR starting — env=%s", settings.APP_ENV)
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    yield
    logger.info("TennisModel KCR shutting down")


app = FastAPI(
    title="TennisModel KCR",
    description="ML-powered tennis predictions — OI rankings, Elo ratings, match analysis",
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── CORS (allow same-origin and localhost dev) ────────────────────────────────
origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"]
if settings.is_production:
    # Add your production domain here when you have it
    origins += ["https://tennismodelkcr.com", "https://www.tennismodelkcr.com"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ── API Routers ───────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(predictions.router)
app.include_router(rankings.router)
app.include_router(players.router)

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_DIR = Path("frontend/static")
TEMPLATE_DIR = Path("frontend/templates")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── SPA catch-all (serve index.html for all non-API routes) ──────────────────
@app.get("/", response_class=HTMLResponse)
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_spa(request: Request, full_path: str = ""):
    # Don't intercept /api routes
    if full_path.startswith("api/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404)

    index = TEMPLATE_DIR / "index.html"
    if index.exists():
        return HTMLResponse(content=index.read_text())

    # Fallback if template not built yet
    return HTMLResponse(content="<h1>TennisModel KCR — Building…</h1>", status_code=503)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    from backend.services.model import is_model_available
    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "model_available": is_model_available(),
        "api_key_set": bool(settings.RAPIDAPI_KEY),
    }

"""
main.py
=======
Entry point FastAPI untuk Twitter/X Scraper backend.

Run:
    uvicorn main:app --reload --port 8002
"""
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logger import get_logger
from app.routers import auth, scrape, profiles, debug, tweets
from app.routers.exports import router as exports_router          # ← TAMBAH INI
from app.services import runner

logger = get_logger("main")


# ── Lifespan (ganti on_event yang deprecated) ─────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("=" * 60)
    logger.info("  TWITTER/X SCRAPER API — STARTING")
    logger.info(f"  Listening on http://{settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"  DEBUG mode: {settings.DEBUG}")
    logger.info(f"  Docs: http://{settings.API_HOST}:{settings.API_PORT}/docs")
    logger.info("=" * 60)

    runner.startup()  # inisialisasi ProcessPoolExecutor

    if settings.DEBUG:
        from app.core import cookie_injector as ci
        logger.info(f"  Session valid: {ci.has_valid_session()}")

    yield

    # Shutdown
    logger.info("Backend shutting down...")
    runner.shutdown()  # tunggu job selesai, cleanup executor


app = FastAPI(
    title="Twitter/X Scraper API",
    description="Backend untuk Twitter/X profile scraper dengan cookie injector & growth tracking",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logging middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.time()
    logger.debug(f"→ {request.method} {request.url.path}")
    try:
        response = await call_next(request)
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        logger.error(
            f"✗ {request.method} {request.url.path} | {elapsed:.0f}ms | {e}\n"
            f"{traceback.format_exc()}"
        )
        raise
    elapsed = (time.time() - t0) * 1000
    logger.debug(
        f"← {request.method} {request.url.path} | {response.status_code} | {elapsed:.0f}ms"
    )
    return response


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(f"UNHANDLED EXCEPTION pada {request.method} {request.url.path}:\n{tb}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"Internal server error: {exc}",
            "timestamp": datetime.now().isoformat(),
            "error": {
                "type": type(exc).__name__,
                "traceback": tb[-3000:] if settings.DEBUG else "Aktifkan DEBUG untuk traceback",
            },
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(scrape.router)
app.include_router(tweets.router)
app.include_router(profiles.router)
app.include_router(debug.router)
app.include_router(exports_router)                                # ← TAMBAH INI


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "name":    "Twitter/X Scraper API",
        "version": "1.0.0",
        "docs":    "/docs",
        "health":  "/api/v1/health",
    }
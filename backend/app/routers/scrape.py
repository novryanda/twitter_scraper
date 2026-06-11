"""
scrape.py — Router scraping profil.
"""
import time
import asyncio
import random
import traceback
from fastapi import APIRouter

from app.core import cookie_injector as ci
from app.core.logger import get_logger
from app.core.responses import success, error
from app.models.schemas import ScrapeProfileRequest, BatchScrapeRequest
from app.services import runner
from app.services import tracking

logger = get_logger("router.scrape")
router = APIRouter(prefix="/api/v1/scrape", tags=["Scrape"])


@router.post("/profile")
async def scrape_profile(req: ScrapeProfileRequest):
    """Scrape satu profil (username/@handle/URL)."""
    if not ci.has_valid_session():
        return error("Session tidak valid — login dulu", 401)

    logger.info(f"Scrape profile request: {req.username}")
    try:
        t0 = time.time()
        result = await runner.run_profile(req.username)
        elapsed = round(time.time() - t0, 2)
        result["_meta"] = {"elapsed_seconds": elapsed}

        if req.save_tracking and result.get("success"):
            tracking.save_snapshot(result)
            result["_tracking_saved"] = True

        if not result.get("success"):
            return error(result.get("error", "Scrape gagal"), 422, result)

        return success(
            result,
            f"Profile @{result.get('username', req.username)} scraped dalam {elapsed}s",
        )
    except Exception as e:
        logger.error(f"Scrape exception: {e}\n{traceback.format_exc()}")
        return error(f"Scrape failed: {e}", 500,
                     {"traceback": traceback.format_exc()[-2000:]})


@router.post("/profiles/batch")
async def scrape_batch(req: BatchScrapeRequest):
    """Batch scrape beberapa profil dengan jeda antar request."""
    if not req.usernames:
        return error("'usernames' harus berupa array non-kosong", 400)
    if not ci.has_valid_session():
        return error("Session tidak valid — login dulu", 401)

    results = []
    t_total = time.time()
    try:
        for i, uname in enumerate(req.usernames):
            logger.info(f"[{i+1}/{len(req.usernames)}] {uname}")
            try:
                r = await runner.run_profile(uname)
                if req.save_tracking and r.get("success"):
                    tracking.save_snapshot(r)

                # ✅ FIX: r sudah dict langsung, bukan {"data": ...}
                results.append({
                    "username": uname,
                    "success":  r.get("success", False),
                    "data":     r.get("data") if r.get("success") else None,
                    "error":    r.get("error"),
                })
            except Exception as e:
                results.append({
                    "username": uname,
                    "success":  False,
                    "data":     None,
                    "error":    str(e),
                })

            if i < len(req.usernames) - 1:
                await asyncio.sleep(req.delay_between + random.randint(3, 8))

    except Exception as e:
        logger.error(f"Batch exception: {e}")
        return error(f"Batch failed: {e}", 500)

    summary = {
        "total":           len(req.usernames),
        "success":         sum(1 for r in results if r["success"]),
        "failed":          sum(1 for r in results if not r["success"]),
        "elapsed_seconds": round(time.time() - t_total, 2),
        "results":         results,
    }
    return success(
        summary,
        f"Batch: {summary['success']}/{summary['total']} sukses",
    )
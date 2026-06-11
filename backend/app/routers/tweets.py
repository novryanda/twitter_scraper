"""
tweets.py — Router untuk scraping tweet/post.
"""
import re
import time
import traceback
from fastapi import APIRouter

from app.core import cookie_injector as ci
from app.core.logger import get_logger
from app.core.responses import success, error
from app.models.schemas import (
    ScrapeUserTweetsRequest,
    ScrapeRepliesRequest,
    ScrapeSearchRequest,
)
from app.services import runner

logger = get_logger("router.tweets")
router = APIRouter(prefix="/api/v1/tweets", tags=["Tweets"])


def _parse_username(raw: str) -> str:
    """
    Terima berbagai format input, kembalikan username bersih.
    - https://x.com/gibran_tweet          → gibran_tweet
    - https://twitter.com/gibran_tweet    → gibran_tweet
    - https://x.com/gibran_tweet?s=20     → gibran_tweet
    - @gibran_tweet                       → gibran_tweet
    - gibran_tweet                        → gibran_tweet
    """
    raw = (raw or "").strip()
    # URL profil Twitter/X
    if "x.com/" in raw or "twitter.com/" in raw:
        m = re.search(r"(?:x|twitter)\.com/([^/?#\s]+)", raw)
        if m:
            return m.group(1)
    # Handle @username
    if raw.startswith("@"):
        return raw[1:]
    return raw


@router.post("/user")
async def scrape_user_tweets(req: ScrapeUserTweetsRequest):
    """
    Scrape tweet dari timeline user.
    Input username bisa berupa:
      - Username: gibran_tweet
      - Dengan @: @gibran_tweet
      - URL profil: https://x.com/gibran_tweet
    """
    if not ci.has_valid_session():
        return error("Session tidak valid — login dulu", 401)

    # ← Parse username dari berbagai format input
    clean_username = _parse_username(req.username)
    if not clean_username:
        return error("Username tidak valid", 400)

    logger.info(f"Scrape user tweets: @{clean_username} (input: {req.username[:50]}) max={req.max_tweets}")
    try:
        t0 = time.time()
        result = await runner.run_user_tweets(
            clean_username,
            max_tweets=req.max_tweets,
            sentiment_mode=req.sentiment_mode,
        )
        elapsed = round(time.time() - t0, 2)

        if not result.get("success"):
            return error(result.get("error", "Scrape gagal"), 422, result)

        result["_meta"] = {"elapsed_seconds": elapsed}
        return success(
            result,
            f"{result.get('tweets_count', 0)} tweets @{clean_username} dalam {elapsed}s",
        )
    except Exception as e:
        logger.error(f"scrape_user_tweets exception: {e}\n{traceback.format_exc()}")
        return error(f"Scrape failed: {e}", 500)


@router.post("/replies")
async def scrape_tweet_replies(req: ScrapeRepliesRequest):
    """
    Scrape tweet utama + reply-nya.
    Input tweet_url harus URL lengkap: https://x.com/user/status/123...
    """
    if not ci.has_valid_session():
        return error("Session tidak valid — login dulu", 401)

    # Validasi harus ada /status/ di URL
    if "/status/" not in req.tweet_url:
        return error(
            "URL tidak valid — harus mengandung /status/<id>. "
            "Contoh: https://x.com/gibran_tweet/status/175829...",
            400,
        )

    logger.info(f"Scrape replies: {req.tweet_url[:60]} sort={req.sort_by}")
    try:
        t0 = time.time()
        result = await runner.run_replies(
            req.tweet_url,
            max_replies=req.max_replies,
            sort_by=req.sort_by,
            sentiment_mode=req.sentiment_mode,
        )
        elapsed = round(time.time() - t0, 2)

        if not result.get("success"):
            return error(result.get("error", "Scrape gagal"), 422, result)

        result["_meta"] = {"elapsed_seconds": elapsed}
        return success(
            result,
            f"{result.get('replies_count', 0)} replies dalam {elapsed}s",
        )
    except Exception as e:
        logger.error(f"scrape_replies exception: {e}\n{traceback.format_exc()}")
        return error(f"Scrape failed: {e}", 500)


@router.post("/search")
async def scrape_search(req: ScrapeSearchRequest):
    """
    Scrape hasil pencarian / hashtag.
    """
    if not ci.has_valid_session():
        return error("Session tidak valid — login dulu", 401)

    logger.info(f"Scrape search: '{req.query}' type={req.search_type}")
    try:
        t0 = time.time()
        result = await runner.run_search(
            req.query,
            max_tweets=req.max_tweets,
            search_type=req.search_type,
            sentiment_mode=req.sentiment_mode,
        )
        elapsed = round(time.time() - t0, 2)

        if not result.get("success"):
            return error(result.get("error", "Scrape gagal"), 422, result)

        result["_meta"] = {"elapsed_seconds": elapsed}
        return success(
            result,
            f"{result.get('tweets_count', 0)} tweets untuk '{req.query}' dalam {elapsed}s",
        )
    except Exception as e:
        logger.error(f"scrape_search exception: {e}\n{traceback.format_exc()}")
        return error(f"Scrape failed: {e}", 500)
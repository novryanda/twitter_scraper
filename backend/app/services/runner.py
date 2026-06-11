"""
runner.py
=========
Menjalankan scraper Playwright (sync API) di PROSES TERPISAH.

KENAPA PROSES, BUKAN THREAD:
  Playwright sync API memanggil loop.run_until_complete() di dalam,
  yang bentrok dengan event loop uvicorn yang sudah berjalan.
  Di Windows (ProactorEventLoop) juga muncul NotImplementedError
  saat subprocess spawn dari thread non-utama.
  ProcessPoolExecutor memberi setiap job event loop bersih sendiri.

DESAIN:
  - Satu ProcessPoolExecutor global (max_workers=1) dibuat saat startup,
    di-shutdown saat aplikasi mati. Tidak spawn ulang tiap request.
  - Setiap job function self-contained (import di dalam fungsi) agar
    picklable dan aman di Windows 'spawn' start method.
  - Timeout per-job via asyncio.wait_for() — default 10 menit.
  - Exception dari child process di-wrap jadi dict error agar router
    tidak perlu tangani ProcessPoolExecutor internals.
  - Auto-save JSON ke folder exports/ setelah scrape berhasil.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import traceback
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from typing import Any, Dict, Optional

# ── Timeout default per job (detik) ──────────────────────────────────────────
DEFAULT_TIMEOUT = 600  # 10 menit — sesuaikan jika scrape besar butuh lebih lama

# ── Folder exports — relatif ke root project (backend/) ──────────────────────
EXPORTS_DIR = os.path.join(os.getcwd(), "exports")

# ── Single global executor — dibuat sekali, reuse antar request ───────────────
_executor: Optional[ProcessPoolExecutor] = None


def startup() -> None:
    """
    Panggil di app startup (lifespan / on_event("startup")).
    Membuat process pool sekali pakai selama lifetime aplikasi.
    """
    global _executor
    if _executor is None:
        _executor = ProcessPoolExecutor(max_workers=1)
    # Pastikan folder exports ada sejak awal
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def shutdown() -> None:
    """
    Panggil di app shutdown (lifespan / on_event("shutdown")).
    Tunggu job yang sedang berjalan selesai, lalu cleanup.
    """
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None


# ── Helpers internal ─────────────────────────────────────────────────────────

def _error_result(msg: str, extra: Optional[Dict] = None) -> Dict:
    result = {"success": False, "error": msg}
    if extra:
        result.update(extra)
    return result


def _sanitize(s: str, max_len: int = 40) -> str:
    """Bersihkan string agar aman dipakai sebagai bagian nama file."""
    s = re.sub(r"[^\w\-]", "_", s or "unknown")
    return s[:max_len].strip("_") or "unknown"


def _save_export(result: Dict, prefix: str) -> Optional[str]:
    """
    Simpan result ke JSON di folder exports/.
    Nama file: <prefix>_<timestamp>.json
    Kembalikan nama file, atau None kalau gagal.
    """
    try:
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{_sanitize(prefix)}_{ts}.json"
        fpath = os.path.join(EXPORTS_DIR, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return fname
    except Exception as e:
        # Jangan sampai save gagal merusak response
        print(f"[runner] _save_export warning: {e}")
        return None


async def _run(fn: Any, *args: Any, timeout: int = DEFAULT_TIMEOUT) -> Dict:
    """
    Jalankan fn(*args) di child process, tunggu secara async.
    Tangani timeout dan exception agar selalu kembalikan dict.
    """
    global _executor
    if _executor is None:
        return _error_result(
            "Process pool belum diinisialisasi — pastikan startup() dipanggil"
        )

    loop = asyncio.get_running_loop()
    try:
        future = loop.run_in_executor(_executor, fn, *args)
        result = await asyncio.wait_for(future, timeout=timeout)
        return result

    except asyncio.TimeoutError:
        return _error_result(
            f"Scrape timeout setelah {timeout}s — "
            "coba kurangi max_tweets/max_replies atau periksa koneksi"
        )
    except FuturesTimeoutError:
        return _error_result(f"Process timeout setelah {timeout}s")

    except Exception as e:
        tb = traceback.format_exc()
        return _error_result(
            f"Scraper error: {type(e).__name__}: {e}",
            {"traceback": tb[-3000:]},
        )


# ── JOB FUNCTIONS — dijalankan di child process ───────────────────────────────

def _profile_job(username_or_url: str) -> Dict:
    try:
        from app.services.profile_scraper import TwitterProfileScraper
        with TwitterProfileScraper() as s:
            return s.scrape_profile(username_or_url)
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "username": username_or_url,
        }


def _user_tweets_job(username: str, max_tweets: int,
                     sentiment_mode: Optional[str]) -> Dict:
    try:
        from app.services.tweet_scraper import TwitterTweetScraper
        with TwitterTweetScraper(sentiment_mode=sentiment_mode) as s:
            return s.scrape_user_tweets(username, max_tweets=max_tweets)
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "username": username,
        }


def _replies_job(tweet_url: str, max_replies: int,
                 sort_by: str, sentiment_mode: Optional[str]) -> Dict:
    try:
        from app.services.tweet_scraper import TwitterTweetScraper
        with TwitterTweetScraper(sentiment_mode=sentiment_mode) as s:
            return s.scrape_tweet_replies(
                tweet_url, max_replies=max_replies, sort_by=sort_by
            )
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "url": tweet_url,
        }


def _search_job(query: str, max_tweets: int,
                search_type: str, sentiment_mode: Optional[str]) -> Dict:
    try:
        from app.services.tweet_scraper import TwitterTweetScraper
        with TwitterTweetScraper(sentiment_mode=sentiment_mode) as s:
            return s.scrape_search(
                query, max_tweets=max_tweets, search_type=search_type
            )
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "query": query,
        }


# ── PUBLIC ASYNC API — dipanggil dari router ─────────────────────────────────

async def run_profile(username_or_url: str) -> Dict:
    return await _run(_profile_job, username_or_url)


async def run_user_tweets(
    username: str,
    max_tweets: int = 40,
    sentiment_mode: Optional[str] = None,
) -> Dict:
    result = await _run(_user_tweets_job, username, max_tweets, sentiment_mode)
    # Auto-save jika berhasil
    if result.get("success"):
        fname = _save_export(result, f"user_{username}")
        if fname:
            result["_export_file"] = fname
    return result


async def run_replies(
    tweet_url: str,
    max_replies: int = 50,
    sort_by: str = "newest",
    sentiment_mode: Optional[str] = None,
) -> Dict:
    result = await _run(_replies_job, tweet_url, max_replies, sort_by, sentiment_mode)
    if result.get("success"):
        # Ambil tweet_id dari URL untuk nama file
        m = __import__("re").search(r"/status/(\d+)", tweet_url)
        tid = m.group(1) if m else "replies"
        fname = _save_export(result, f"replies_{tid}")
        if fname:
            result["_export_file"] = fname
    return result


async def run_search(
    query: str,
    max_tweets: int = 40,
    search_type: str = "Latest",
    sentiment_mode: Optional[str] = None,
) -> Dict:
    result = await _run(_search_job, query, max_tweets, search_type, sentiment_mode)
    if result.get("success"):
        fname = _save_export(result, f"search_{query}")
        if fname:
            result["_export_file"] = fname
    return result
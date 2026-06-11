"""
login_worker.py
===============
Worker untuk login Twitter/X via browser (async Playwright di thread terpisah).
Auto-save session cookies setelah login terdeteksi.

State login disimpan thread-safe untuk dipoll via endpoint /auth/status.
"""
import os
import time
import asyncio
import threading
from datetime import datetime
from typing import Dict

from app.core.config import settings
from app.core.logger import get_logger
from app.core import cookie_injector as ci

logger = get_logger("login_worker")

_login_state: Dict = {
    "is_running":        False,
    "browser_opened_at": None,
    "login_detected":    False,
    "username":          None,
    "last_error":        None,
}
_state_lock = threading.Lock()


def update_state(**kwargs):
    with _state_lock:
        _login_state.update(kwargs)


def get_state() -> Dict:
    with _state_lock:
        return dict(_login_state)


def run_login_browser(timeout_minutes: int = 5, headless: bool = False):
    """Mulai browser login di background thread."""

    async def _worker():
        from playwright.async_api import async_playwright
        logger.info("Membuka browser untuk login...")
        update_state(is_running=True, browser_opened_at=datetime.now().isoformat(),
                     login_detected=False, last_error=None, username=None)
        try:
            async with async_playwright() as p:
                context = await p.chromium.launch_persistent_context(
                    settings.TWITTER_PROFILE,
                    headless=headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-notifications", "--no-sandbox", "--disable-infobars",
                        "--disable-setuid-sandbox", "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                    viewport=None,
                    user_agent=settings.USER_AGENT,
                    locale="en-US", timezone_id="Asia/Jakarta",
                )
                page = context.pages[0] if context.pages else await context.new_page()

                # Inject cookies dari session file jika ada
                try:
                    if ci.has_valid_session():
                        n = await ci.inject_cookies_async(context)
                        logger.info(f"{n} cookies diinject dari session file")
                except Exception as e:
                    logger.warning(f"Cookie inject warning: {e}")

                await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)

                names = {c["name"] for c in await context.cookies()}
                if "auth_token" in names and "ct0" in names and "login" not in page.url:
                    logger.info("Sudah login!")
                    await _save_session(context)
                    update_state(login_detected=True)
                    await asyncio.sleep(3)
                    await context.close()
                    return

                await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                logger.info("Menunggu login manual...")

                logged_in = False
                for i in range(timeout_minutes * 12):
                    await asyncio.sleep(5)
                    names = {c["name"] for c in await context.cookies()}
                    if "auth_token" in names and "ct0" in names and "login" not in page.url:
                        logged_in = True
                        logger.info("Login berhasil!")
                        break

                if not logged_in:
                    logger.warning("Timeout — login tidak terdeteksi")
                    update_state(last_error="Timeout: user tidak login tepat waktu")
                    await context.close()
                    return

                await asyncio.sleep(3)
                await _save_session(context)
                update_state(login_detected=True)
                await context.close()
        except Exception as e:
            logger.error(f"Login worker error: {e}")
            update_state(last_error=str(e))
        finally:
            update_state(is_running=False)

    async def _save_session(ctx):
        try:
            cookies = await ctx.cookies()
            tw_cookies = [
                {"name": c["name"], "value": c["value"],
                 "domain": c.get("domain", ".x.com"), "path": c.get("path", "/"),
                 "httpOnly": c.get("httpOnly", False), "secure": c.get("secure", True),
                 "sameSite": c.get("sameSite", "Lax"), "expirationDate": c.get("expires", -1)}
                for c in cookies
                if any(td in c.get("domain", "") for td in ["x.com", "twitter.com"])
            ]
            ci.save_session(tw_cookies, note="auto_saved_from_browser_login")
            logger.info(f"{len(tw_cookies)} cookies tersimpan")
        except Exception as e:
            logger.warning(f"Gagal simpan session: {e}")

    thread = threading.Thread(target=lambda: asyncio.run(_worker()), daemon=True)
    thread.start()
    return thread

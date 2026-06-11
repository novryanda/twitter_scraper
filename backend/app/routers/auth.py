"""
auth.py — Router autentikasi & session management.
"""
import os
import time
import shutil
from fastapi import APIRouter

from app.core import cookie_injector as ci
from app.core.config import settings
from app.core.logger import get_logger
from app.core.responses import success, error
from app.models.schemas import CookieImportRequest, LoginBrowserRequest, LogoutRequest
from app.services import login_worker

logger = get_logger("router.auth")
router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/import-cookies")
def import_cookies(req: CookieImportRequest):
    """Import cookies dari Cookie-Editor (JSON array)."""
    cookies = req.cookies
    if not isinstance(cookies, list) or not cookies:
        return error("Cookies harus berupa array non-kosong", 400)

    names = {c.get("name", "") for c in cookies if isinstance(c, dict)}
    missing = ci.REQUIRED_COOKIES - names
    if missing:
        return error(f"Cookie wajib tidak ada: {', '.join(missing)}", 400,
                     {"required": list(ci.REQUIRED_COOKIES)})

    tw_cookies = [c for c in cookies if isinstance(c, dict) and any(
        td in str(c.get("domain", "")).lower()
        for td in ["x.com", "twitter.com", "twimg.com"])]
    if not tw_cookies:
        tw_cookies = cookies

    path = ci.save_session(tw_cookies, username=req.username or "")
    info = ci.get_session_info()
    logger.info(f"Import cookies sukses: {len(tw_cookies)} cookies")
    return success({"session_file": path, "total_cookies": len(tw_cookies),
                    "session_info": info}, "Cookies berhasil diimport")


@router.get("/status")
def auth_status():
    """Cek status login / session."""
    state = login_worker.get_state()
    valid = ci.has_valid_session()
    info  = ci.get_session_info()
    profile_exists = os.path.exists(settings.TWITTER_PROFILE) and bool(os.listdir(settings.TWITTER_PROFILE))

    return success({
        "is_running":         state["is_running"],
        "login_detected":     state["login_detected"],
        "username":           state["username"] or info.get("username", ""),
        "browser_opened_at":  state["browser_opened_at"],
        "last_error":         state["last_error"],
        "session_valid":      valid,
        "session_info":       info,
        "profile_dir_exists": profile_exists,
        "is_logged_in":       valid or (state["login_detected"] and profile_exists),
    }, "Session valid — siap scraping" if valid else "Belum login")


@router.get("/session-info")
def session_info():
    return success(ci.get_session_info(), "Session info")


@router.post("/login")
def login_browser(req: LoginBrowserRequest):
    """Buka browser untuk login manual."""
    state = login_worker.get_state()
    if state["is_running"]:
        return error("Browser login sedang berjalan", 409,
                     {"browser_opened_at": state["browser_opened_at"]})
    login_worker.run_login_browser(req.timeout_minutes, req.headless)
    time.sleep(2)
    return success({"browser_started": True, "timeout_minutes": req.timeout_minutes,
                    "instructions": ["Browser akan terbuka", "Login manual ke Twitter/X",
                                     "Selesaikan 2FA jika diminta",
                                     "Tunggu timeline beranda muncul",
                                     "Cek status via GET /api/v1/auth/status"]},
                   f"Browser login dibuka (timeout {req.timeout_minutes} menit)")


@router.post("/logout")
def logout(req: LogoutRequest):
    state = login_worker.get_state()
    if state["is_running"]:
        return error("Browser sedang berjalan", 409)
    deleted = ci.delete_session()
    if req.hard_reset and os.path.exists(settings.TWITTER_PROFILE):
        # Hapus ISI folder saja — tidak hapus direktori itu sendiri karena
        # di Docker, folder ini adalah volume mount point (rmtree gagal Errno 16)
        for item in os.listdir(settings.TWITTER_PROFILE):
            item_path = os.path.join(settings.TWITTER_PROFILE, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.unlink(item_path)
        login_worker.update_state(login_detected=False, username=None, last_error=None)
        return success({"session_deleted": deleted, "profile_reset": True}, "Hard reset berhasil")
    login_worker.update_state(login_detected=False, username=None)
    return success({"session_deleted": deleted}, "Logout berhasil")

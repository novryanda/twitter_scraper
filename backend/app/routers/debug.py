"""
debug.py — Router debug & health untuk memudahkan troubleshooting.
"""
import os
import sys
import platform
from datetime import datetime
from fastapi import APIRouter

from app.core.config import settings
from app.core.logger import get_logger, read_recent_logs, LOG_FILE
from app.core.responses import success
from app.core import cookie_injector as ci
from app.services import tracking, login_worker

logger = get_logger("router.debug")
router = APIRouter(prefix="/api/v1", tags=["Debug / Health"])


@router.get("/health")
def health():
    """Health check menyeluruh — status session, file, tracking."""
    valid = ci.has_valid_session()
    endpoints_ok = os.path.exists(os.path.join(os.getcwd(), "twitter_endpoints.json"))
    profile_exists = os.path.exists(settings.TWITTER_PROFILE) and bool(os.listdir(settings.TWITTER_PROFILE))

    return success({
        "api": "running",
        "version": "1.0",
        "platform": "twitter",
        "session_valid": valid,
        "session_info": ci.get_session_info(),
        "endpoints_file_exists": endpoints_ok,
        "profile_dir_exists": profile_exists,
        "tracked_profiles": len(tracking.load_tracking()),
        "login_state": login_worker.get_state(),
        "debug_mode": settings.DEBUG,
        "timestamp": datetime.now().isoformat(),
    }, "Backend healthy")


@router.get("/debug/logs")
def get_logs(lines: int = 200):
    """Ambil N baris log terakhir (untuk panel debug di frontend)."""
    return success({
        "log_file": LOG_FILE,
        "lines_requested": lines,
        "logs": read_recent_logs(lines),
    }, "Logs retrieved")


@router.get("/debug/system")
def system_info():
    """Info sistem untuk diagnosa."""
    return success({
        "python_version": sys.version,
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "debug_mode": settings.DEBUG,
        "config": {
            "api_host": settings.API_HOST,
            "api_port": settings.API_PORT,
            "headless": settings.HEADLESS,
            "cors_origins": settings.CORS_ORIGINS,
            "min_gap_seconds": settings.MIN_GAP_SECONDS,
        },
        "paths": {
            "data_dir": settings.DATA_DIR,
            "output_profile_dir": settings.OUTPUT_PROFILE_DIR,
            "session_dir": settings.SESSION_DIR,
            "twitter_profile": settings.TWITTER_PROFILE,
        },
    }, "System info")


@router.delete("/debug/logs")
def clear_logs():
    """Kosongkan file log."""
    try:
        open(LOG_FILE, "w").close()
        logger.info("Log file dikosongkan via endpoint")
        return success({"cleared": True}, "Logs cleared")
    except Exception as e:
        return success({"cleared": False, "error": str(e)}, "Gagal clear logs")

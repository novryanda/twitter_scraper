"""
profiles.py — Router analytics / growth tracking.
"""
import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.logger import get_logger
from app.core.responses import success, error
from app.models.schemas import ManualTrackRequest
from app.services import tracking

logger = get_logger("router.profiles")
router = APIRouter(prefix="/api/v1/profiles", tags=["Profiles / Growth"])


@router.get("")
def list_profiles():
    users = tracking.list_profiles()
    return success({"count": len(users), "users": users})


@router.get("/{username}")
def get_profile(username: str):
    data = tracking.get_profile(username)
    if not data:
        return error(f"Tidak ada data untuk @{username}", 404)
    return success(data)


@router.get("/{username}/growth")
def growth(username: str, days: int = 30):
    result = tracking.analyze_growth(username, days)
    if "error" in result:
        return error(result["error"], 400)
    return success(result, f"Growth analysis @{username}")


@router.post("/track")
def manual_track(req: ManualTrackRequest):
    if not req.followers and not req.tweets:
        return error("Minimal 'followers' atau 'tweets' harus diisi", 400)
    result = tracking.manual_snapshot(req.username, req.followers, req.following,
                                      req.tweets, req.likes, req.scraped_at)
    return success(result, f"Manual snapshot ditambahkan untuk @{req.username}")


@router.delete("/{username}")
def delete_profile(username: str):
    if tracking.delete_profile(username):
        return success({"deleted": username}, f"Data @{username} dihapus")
    return error(f"@{username} tidak ditemukan", 404)


@router.get("/{username}/export-csv")
def export_csv(username: str):
    fp = tracking.export_csv(username)
    if not fp or not os.path.exists(fp):
        return error(f"Tidak ada data untuk @{username}", 404)
    return FileResponse(fp, media_type="text/csv", filename=os.path.basename(fp))

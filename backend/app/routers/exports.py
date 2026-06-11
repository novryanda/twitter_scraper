"""
exports.py — Router untuk manajemen file hasil scrape (JSON).

Endpoint:
  GET  /api/v1/exports          → list semua file di folder exports/
  GET  /api/v1/exports/{fname}  → download 1 file JSON
  DELETE /api/v1/exports/{fname}→ hapus 1 file
"""
import os
import json
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.core.logger import get_logger
from app.core.responses import success, error

logger = get_logger("router.exports")
router = APIRouter(prefix="/api/v1/exports", tags=["Exports"])

# Folder penyimpanan — selalu relatif ke root project (backend/)
EXPORTS_DIR = os.path.join(os.getcwd(), "exports")


def _ensure_dir():
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def _safe_filename(fname: str) -> bool:
    """Cegah path traversal — hanya izinkan karakter aman."""
    return (
        fname.endswith(".json")
        and ".." not in fname
        and "/" not in fname
        and "\\" not in fname
    )


@router.get("")
async def list_exports():
    """Kembalikan daftar semua file JSON di folder exports/."""
    _ensure_dir()
    try:
        files = []
        for fname in sorted(os.listdir(EXPORTS_DIR), reverse=True):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(EXPORTS_DIR, fname)
            stat  = os.stat(fpath)
            # Baca baris pertama untuk peek metadata
            meta = {}
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    meta = {
                        "mode":         data.get("mode", ""),
                        "username":     data.get("username") or data.get("query") or "",
                        "tweets_count": data.get("tweets_count") or data.get("replies_count") or 0,
                        "scraped_at":   data.get("scraped_at", ""),
                    }
            except Exception:
                pass

            files.append({
                "filename":   fname,
                "size_bytes": stat.st_size,
                "size_kb":    round(stat.st_size / 1024, 1),
                "modified":   datetime.fromtimestamp(stat.st_mtime).isoformat(),
                **meta,
            })

        return success(
            {"files": files, "total": len(files), "exports_dir": EXPORTS_DIR},
            f"{len(files)} file ditemukan",
        )
    except Exception as e:
        logger.error(f"list_exports error: {e}")
        return error(f"Gagal membaca folder exports: {e}", 500)


@router.get("/{filename}")
async def download_export(filename: str):
    """Download file JSON berdasarkan nama file."""
    if not _safe_filename(filename):
        return error("Nama file tidak valid", 400)

    _ensure_dir()
    fpath = os.path.join(EXPORTS_DIR, filename)
    if not os.path.isfile(fpath):
        return error(f"File '{filename}' tidak ditemukan", 404)

    return FileResponse(
        path=fpath,
        media_type="application/json",
        filename=filename,
    )


@router.delete("/{filename}")
async def delete_export(filename: str):
    """Hapus file export berdasarkan nama file."""
    if not _safe_filename(filename):
        return error("Nama file tidak valid", 400)

    _ensure_dir()
    fpath = os.path.join(EXPORTS_DIR, filename)
    if not os.path.isfile(fpath):
        return error(f"File '{filename}' tidak ditemukan", 404)

    try:
        os.remove(fpath)
        logger.info(f"File dihapus: {filename}")
        return success({"filename": filename}, f"File '{filename}' berhasil dihapus")
    except Exception as e:
        logger.error(f"delete_export error: {e}")
        return error(f"Gagal menghapus file: {e}", 500)
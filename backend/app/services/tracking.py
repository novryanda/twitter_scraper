"""
tracking.py
===========
Service untuk growth tracking & analisis pertumbuhan profil.
Menyimpan snapshot followers/following/tweets/likes ke growth_tracking.json.
"""
import os
import json
import csv
from datetime import datetime, timedelta
from typing import Dict, List

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("tracking")

TRACKING_FILE = settings.TRACKING_FILE


def load_tracking() -> Dict:
    if not os.path.exists(TRACKING_FILE):
        return {}
    try:
        with open(TRACKING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Gagal load tracking: {e}")
        return {}


def save_tracking(data: Dict):
    os.makedirs(settings.OUTPUT_PROFILE_DIR, exist_ok=True)
    with open(TRACKING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_snapshot(profile_result: Dict) -> bool:
    """Simpan hasil scrape profil ke tracking. Hindari duplikat per hari."""
    try:
        data = profile_result.get("data", {}) or {}
        username = data.get("username") or profile_result.get("username", "")
        if not username:
            return False

        tracking = load_tracking()
        scraped_at = data.get("scraped_at", datetime.now().isoformat())

        if username not in tracking:
            tracking[username] = {"username": username,
                                  "first_tracked": scraped_at, "history": []}

        snapshot = {
            "scraped_at": scraped_at,
            "followers":  data.get("followers", 0),
            "following":  data.get("following", 0),
            "tweets":     data.get("tweets", 0),
            "likes":      data.get("likes", 0),
        }

        today = scraped_at[:10]
        history = tracking[username].get("history", [])
        updated = False
        for h in history:
            if h.get("scraped_at", "")[:10] == today:
                h.update(snapshot); updated = True; break
        if not updated:
            tracking[username]["history"].append(snapshot)

        tracking[username]["last_tracked"] = scraped_at
        save_tracking(tracking)
        logger.info(f"Tracking updated: @{username}")
        return True
    except Exception as e:
        logger.error(f"Gagal simpan snapshot: {e}")
        return False


def manual_snapshot(username: str, followers: int, following: int,
                    tweets: int, likes: int, scraped_at: str = None) -> Dict:
    username = username.lstrip("@").lower()
    scraped_at = scraped_at or datetime.now().isoformat()
    tracking = load_tracking()
    if username not in tracking:
        tracking[username] = {"username": username,
                              "first_tracked": scraped_at, "history": []}
    snapshot = {"scraped_at": scraped_at, "followers": followers,
                "following": following, "tweets": tweets, "likes": likes}
    tracking[username]["history"].append(snapshot)
    tracking[username]["last_tracked"] = scraped_at
    save_tracking(tracking)
    return {"username": username, "snapshot": snapshot,
            "total_data_points": len(tracking[username]["history"])}


def list_profiles() -> List[Dict]:
    tracking = load_tracking()
    users = []
    for username, data in tracking.items():
        history = data.get("history", [])
        latest = history[-1] if history else {}
        users.append({
            "username":          username,
            "data_points":       len(history),
            "first_tracked":     data.get("first_tracked", ""),
            "last_tracked":      data.get("last_tracked", ""),
            "current_followers": latest.get("followers", 0),
            "current_following": latest.get("following", 0),
            "current_tweets":    latest.get("tweets", 0),
            "current_likes":     latest.get("likes", 0),
        })
    users.sort(key=lambda x: x["last_tracked"], reverse=True)
    return users


def get_profile(username: str) -> Dict:
    username = username.lstrip("@").lower()
    tracking = load_tracking()
    if username not in tracking:
        return {}
    data = tracking[username]
    history = data.get("history", [])
    return {
        "username":        username,
        "data_points":     len(history),
        "first_tracked":   data.get("first_tracked", ""),
        "last_tracked":    data.get("last_tracked", ""),
        "latest_snapshot": history[-1] if history else {},
        "history":         sorted(history, key=lambda x: x.get("scraped_at", "")),
    }


def analyze_growth(username: str, days: int = 30) -> Dict:
    username = username.lstrip("@").lower()
    tracking = load_tracking()
    if username not in tracking:
        return {"error": f"Tidak ada data untuk @{username}"}

    history = tracking[username].get("history", [])
    if len(history) < 2:
        return {"error": f"Hanya {len(history)} data point, perlu minimal 2"}

    cutoff = datetime.now() - timedelta(days=days)
    filtered = [h for h in history
                if datetime.fromisoformat(h["scraped_at"]) >= cutoff]
    if len(filtered) < 2:
        filtered = history

    filtered.sort(key=lambda x: x["scraped_at"])
    first, last = filtered[0], filtered[-1]
    first_dt = datetime.fromisoformat(first["scraped_at"])
    last_dt  = datetime.fromisoformat(last["scraped_at"])
    days_span = (last_dt - first_dt).days or 1

    def calc(field):
        s = first.get(field, 0); e = last.get(field, 0); g = e - s
        return {"start": s, "end": e, "growth": g,
                "growth_pct": round(g / s * 100, 2) if s > 0 else 0.0,
                "avg_per_day": round(g / days_span, 2)}

    return {
        "username": username,
        "analyzed_at": datetime.now().isoformat(),
        "period": {"start_date": first_dt.isoformat(), "end_date": last_dt.isoformat(),
                   "days": days_span, "data_points": len(filtered)},
        "followers": calc("followers"),
        "following": calc("following"),
        "tweets":    calc("tweets"),
        "likes":     calc("likes"),
        "history":   filtered,
    }


def delete_profile(username: str) -> bool:
    username = username.lstrip("@").lower()
    tracking = load_tracking()
    if username not in tracking:
        return False
    del tracking[username]
    save_tracking(tracking)
    logger.info(f"Data @{username} dihapus")
    return True


def export_csv(username: str) -> str:
    username = username.lstrip("@").lower()
    tracking = load_tracking()
    if username not in tracking:
        return ""
    history = tracking[username].get("history", [])
    if not history:
        return ""
    fp = os.path.join(settings.OUTPUT_PROFILE_DIR, f"{username}_growth_history.csv")
    with open(fp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Followers", "Following", "Tweets", "Likes"])
        for h in sorted(history, key=lambda x: x["scraped_at"]):
            w.writerow([h["scraped_at"][:19].replace("T", " "),
                        h.get("followers", 0), h.get("following", 0),
                        h.get("tweets", 0), h.get("likes", 0)])
    return fp

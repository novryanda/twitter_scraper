"""
cookie_injector.py
==================
Manajemen session Twitter/X via cookies (mirip Instagram injector).

Cara kerja:
  1. User export cookies dari Cookie-Editor (format JSON)
  2. Cookies disimpan ke session/tw_session.json
  3. inject_cookies_* dipakai untuk inject ke Playwright context
  4. has_valid_session() / get_session_info() untuk cek status

Cookies wajib : auth_token, ct0
Cookies penting: twid, kdt, guest_id
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

from app.core.logger import get_logger

logger = get_logger("cookie_injector")

# ── PATHS ───────────────────────────────────────────────────────────────────
SESSION_DIR  = os.path.join(os.getcwd(), "session")
SESSION_FILE = os.path.join(SESSION_DIR, "tw_session.json")

os.makedirs(SESSION_DIR, exist_ok=True)

# ── COOKIE REQUIREMENTS ─────────────────────────────────────────────────────
REQUIRED_COOKIES  = {"auth_token", "ct0"}
PREFERRED_COOKIES = {"twid", "kdt", "guest_id", "auth_multi"}


# ─────────────────────────────────────────────────────────────────────────────
# SAVE / LOAD
# ─────────────────────────────────────────────────────────────────────────────

def save_session(cookies: List[Dict], username: str = "", note: str = "") -> str:
    """Simpan cookies ke session file dengan metadata."""
    os.makedirs(SESSION_DIR, exist_ok=True)

    normalized = []
    for c in cookies:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        normalized.append({
            "name":           c.get("name", ""),
            "value":          c.get("value", ""),
            "domain":         c.get("domain", ".x.com"),
            "path":           c.get("path", "/"),
            "httpOnly":       c.get("httpOnly", False),
            "secure":         c.get("secure", True),
            "sameSite":       c.get("sameSite", "Lax"),
            "expirationDate": c.get("expirationDate") or c.get("expires", -1),
        })

    payload = {
        "saved_at":   datetime.now().isoformat(),
        "username":   username,
        "note":       note,
        "cookies":    normalized,
    }

    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info(f"Session disimpan: {len(normalized)} cookies (user=@{username or '-'})")
    return SESSION_FILE


def load_session() -> Optional[Dict]:
    """Load full session payload (dengan metadata)."""
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Gagal load session: {e}")
        return None


def load_raw_cookies() -> List[Dict]:
    """Load list cookies saja (tanpa metadata)."""
    payload = load_session()
    if not payload:
        return []
    # Support format lama (list langsung) maupun baru (dict berisi 'cookies')
    if isinstance(payload, list):
        return payload
    return payload.get("cookies", [])


def delete_session() -> bool:
    """Hapus session file."""
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
            logger.info("Session dihapus")
            return True
        return False
    except Exception as e:
        logger.error(f"Gagal hapus session: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────────────────────────────────────────

def _is_cookie_expired(cookie: Dict) -> bool:
    exp = cookie.get("expirationDate") or cookie.get("expires", -1)
    try:
        exp = float(exp)
    except (ValueError, TypeError):
        return False
    if exp == -1:
        return False  # session cookie, tidak expired by date
    return exp < datetime.now().timestamp()


def has_valid_session() -> bool:
    """Cek apakah ada session dengan auth_token + ct0 yang belum expired."""
    cookies = load_raw_cookies()
    if not cookies:
        return False

    names = {c.get("name", "") for c in cookies}
    if not REQUIRED_COOKIES.issubset(names):
        return False

    # Cek required cookies belum expired
    for c in cookies:
        if c.get("name") in REQUIRED_COOKIES and _is_cookie_expired(c):
            return False
    return True


def get_session_info() -> Dict:
    """Detail session untuk ditampilkan ke user."""
    payload = load_session()
    if not payload:
        return {"valid": False, "error": "Session file tidak ditemukan"}

    cookies = load_raw_cookies()
    if not cookies:
        return {"valid": False, "error": "Tidak ada cookies di session file"}

    names = {c.get("name", "") for c in cookies}
    missing_required = REQUIRED_COOKIES - names
    expired = [c.get("name") for c in cookies
               if c.get("name") in REQUIRED_COOKIES and _is_cookie_expired(c)]

    def preview(cookie_name):
        for c in cookies:
            if c.get("name") == cookie_name:
                val = str(c.get("value", ""))
                return f"{val[:10]}...{val[-4:]}" if len(val) > 14 else val
        return ""

    valid = not missing_required and not expired

    return {
        "valid":              valid,
        "session_file":       SESSION_FILE,
        "saved_at":           payload.get("saved_at", "") if isinstance(payload, dict) else "",
        "username":           payload.get("username", "") if isinstance(payload, dict) else "",
        "total_cookies":      len(cookies),
        "cookie_names":       sorted(names),
        "auth_token_preview": preview("auth_token"),
        "ct0_preview":        preview("ct0"),
        "has_preferred":      PREFERRED_COOKIES.issubset(names),
        "preferred_missing":  sorted(PREFERRED_COOKIES - names),
        "missing_required":   sorted(missing_required),
        "expired_cookies":    expired,
        "error":              (f"Cookie wajib hilang: {', '.join(missing_required)}"
                               if missing_required else
                               (f"Cookie expired: {', '.join(expired)}" if expired else "")),
    }


# ─────────────────────────────────────────────────────────────────────────────
# INJECT KE PLAYWRIGHT
# ─────────────────────────────────────────────────────────────────────────────

def _to_playwright_cookies(cookies: List[Dict]) -> List[Dict]:
    """Konversi format Cookie-Editor → format Playwright add_cookies."""
    pw_cookies = []
    samesite_map = {"lax": "Lax", "strict": "Strict", "none": "None",
                    "no_restriction": "None", "unspecified": "Lax"}

    for c in cookies:
        name   = c.get("name")
        value  = c.get("value")
        if not name or value is None:
            continue

        domain = c.get("domain", ".x.com")
        if not domain.startswith("."):
            domain = "." + domain.lstrip(".")

        ss_raw = str(c.get("sameSite", "Lax")).lower()
        same_site = samesite_map.get(ss_raw, "Lax")

        pw = {
            "name":     name,
            "value":    str(value),
            "domain":   domain,
            "path":     c.get("path", "/"),
            "httpOnly": bool(c.get("httpOnly", False)),
            "secure":   bool(c.get("secure", True)),
            "sameSite": same_site,
        }

        exp = c.get("expirationDate") or c.get("expires", -1)
        try:
            exp = float(exp)
            if exp > 0:
                pw["expires"] = exp
        except (ValueError, TypeError):
            pass

        pw_cookies.append(pw)
    return pw_cookies


def inject_cookies_sync(context) -> int:
    """Inject cookies ke Playwright sync BrowserContext. Return jumlah cookie."""
    cookies = load_raw_cookies()
    if not cookies:
        logger.warning("Tidak ada cookies untuk diinject")
        return 0
    pw_cookies = _to_playwright_cookies(cookies)
    context.add_cookies(pw_cookies)
    logger.info(f"{len(pw_cookies)} cookies diinject (sync)")
    return len(pw_cookies)


async def inject_cookies_async(context) -> int:
    """Inject cookies ke Playwright async BrowserContext. Return jumlah cookie."""
    cookies = load_raw_cookies()
    if not cookies:
        logger.warning("Tidak ada cookies untuk diinject")
        return 0
    pw_cookies = _to_playwright_cookies(cookies)
    await context.add_cookies(pw_cookies)
    logger.info(f"{len(pw_cookies)} cookies diinject (async)")
    return len(pw_cookies)

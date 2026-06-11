"""
profile_scraper.py
==================
Twitter/X Profile Scraper — GraphQL Primary + DOM Fallback + HTML Meta.

Strategi:
  1. GraphQL UserByScreenName (paling akurat, butuh endpoints + cookies)
  2. DOM parsing via Playwright (fallback)
  3. HTML meta tags (last resort)

Auth: cookie-based via app.core.cookie_injector

FIXES:
  - parse_number disinkronkan dengan CLI (remove titik sebelum int-cast)
  - Followers selector: coba verified_followers DULU, baru followers
  - Followers fallback via JavaScript DOM scan
  - Kondisi return DOM: cukup display_name ada (tidak perlu followers > 0)
  - Scroll lebih dalam + ekstra wait sebelum baca stats
"""
import os
import re
import json
import time
import random
import requests
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urlparse, unquote

from playwright.sync_api import sync_playwright, Page, BrowserContext

from app.core.config import settings
from app.core.logger import get_logger
from app.core import cookie_injector as ci

logger = get_logger("profile_scraper")

ENDPOINTS_FILE = os.path.join(os.getcwd(), "twitter_endpoints.json")


# ── HELPERS ──────────────────────────────────────────────────────────────────

def parse_username_from_input(raw: str) -> str:
    """Resolve username dari URL / @handle / plain username."""
    raw = raw.strip()
    if "x.com" in raw.lower() or "twitter.com" in raw.lower():
        if not raw.startswith("http"):
            raw = "https://" + raw
        try:
            parsed = urlparse(raw)
            parts  = [p for p in parsed.path.strip("/").split("/") if p]
            if parts:
                username = parts[0].lstrip("@")
                if username.lower() not in (
                    "home", "explore", "notifications", "messages",
                    "i", "settings", "compose", "search", "login",
                ):
                    return username
        except Exception:
            pass
        match = re.search(r'(?:x\.com|twitter\.com)/([a-zA-Z0-9_]+)', raw, re.IGNORECASE)
        if match:
            return match.group(1)

    username = raw.lstrip("@").strip()
    if re.match(r'^[a-zA-Z0-9_]{1,50}$', username):
        return username
    raise ValueError(f"Tidak bisa parse username dari: {raw}")


def parse_number(text: str) -> int:
    """
    Parse angka dengan suffix K/M/B.
    DISINKRONKAN dengan CLI (_parse_number di twitter_profile_scraper.py):
      - Hapus koma DAN titik sebelum int cast
      - Handle "1.9K" → 1900, "9,751" → 9751, "1.2M" → 1200000
    """
    if not text:
        return 0
    text = str(text).strip().upper().replace(",", "")
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    for suffix, mult in multipliers.items():
        if text.endswith(suffix) or (suffix in text and text.index(suffix) == len(text) - 1):
            try:
                return int(float(text.replace(suffix, "")) * mult)
            except Exception:
                return 0
    # Hapus titik untuk handle format "9.751" (ribuan dengan titik)
    try:
        return int(float(text.replace(".", "")))
    except Exception:
        try:
            return int(float(text))
        except Exception:
            return 0


# ── MAIN SCRAPER ─────────────────────────────────────────────────────────────

class TwitterProfileScraper:

    def __init__(self):
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.session: Optional[requests.Session] = None
        self._last_scrape_time = 0.0
        self.endpoints: Dict = {}
        self._load_endpoints()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── ENDPOINTS ─────────────────────────────────────────────────────────
    def _load_endpoints(self):
        if not os.path.exists(ENDPOINTS_FILE):
            logger.warning(f"{ENDPOINTS_FILE} tidak ada — GraphQL strategy dilewati")
            self.endpoints = {"bearer_token": settings.FALLBACK_BEARER, "operations": {}}
            return
        try:
            with open(ENDPOINTS_FILE, "r", encoding="utf-8") as f:
                self.endpoints = json.load(f)
            if not self.endpoints.get("bearer_token"):
                self.endpoints["bearer_token"] = settings.FALLBACK_BEARER
            logger.info(f"Endpoints loaded: {len(self.endpoints.get('operations', {}))} operasi")
        except Exception as e:
            logger.error(f"Gagal load endpoints: {e}")
            self.endpoints = {"bearer_token": settings.FALLBACK_BEARER, "operations": {}}

    # ── BROWSER ───────────────────────────────────────────────────────────
    def _build_context(self):
        self.playwright = sync_playwright().start()
        stealth = """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
            delete navigator.__proto__.webdriver;
        """
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-notifications", "--no-sandbox", "--mute-audio",
            "--disable-infobars", "--no-first-run",
            "--disable-setuid-sandbox", "--disable-dev-shm-usage",
            "--disable-gpu",
        ]
        if not settings.HEADLESS:
            args.append("--start-maximized")
        if settings.PROXY:
            args.append(f"--proxy-server={settings.PROXY}")

        ctx = self.playwright.chromium.launch_persistent_context(
            settings.TWITTER_PROFILE,
            headless=settings.HEADLESS,
            args=args,
            viewport=None if not settings.HEADLESS else {"width": 1366, "height": 800},
            user_agent=settings.USER_AGENT,
            locale="en-US",
            timezone_id="Asia/Jakarta",
        )
        ctx.on("page", lambda p: p.add_init_script(stealth))
        return ctx

    def _is_logged_in(self) -> bool:
        try:
            names = {c["name"] for c in self.context.cookies()}
            return "auth_token" in names and "ct0" in names
        except Exception:
            return False

    def initialize_browser(self):
        if self.context:
            return
        logger.info("Membuka browser Playwright...")
        self.context = self._build_context()

        try:
            if ci.has_valid_session():
                n = ci.inject_cookies_sync(self.context)
                logger.info(f"{n} cookies diinject dari session file")
            else:
                logger.warning("Session file tidak valid — pakai profile dir saja")
        except Exception as e:
            logger.warning(f"Cookie inject warning: {e}")

        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

        def block_heavy(route):
            rt  = route.request.resource_type
            url = route.request.url.lower()
            cdns = ["pbs.twimg.com", "abs.twimg.com", "twimg.com", "x.com", "twitter.com"]
            is_tw = any(c in url for c in cdns)
            if rt in ["image", "media", "font"]:
                route.continue_() if (is_tw or "favicon" in url) else route.abort()
            else:
                route.continue_()

        self.page.route("**/*", block_heavy)
        self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        if "login" in self.page.url or "/i/flow" in self.page.url:
            logger.error("Session expired — redirect ke login")
            self.close()
            raise RuntimeError("Session expired — silakan login ulang via cookie injector")

        if not self._is_logged_in():
            logger.error("Tidak terdeteksi login")
            self.close()
            raise RuntimeError("Tidak login — silakan import cookies dulu")

        self._build_requests_session()
        logger.info("Browser siap (LOGGED IN)")

    def _build_requests_session(self):
        sess = requests.Session()
        cookies = self.context.cookies()
        for c in cookies:
            sess.cookies.set(c["name"], c["value"], domain=c.get("domain", ".x.com"))
        ct0    = next((c["value"] for c in cookies if c["name"] == "ct0"), "")
        bearer = self.endpoints.get("bearer_token") or settings.FALLBACK_BEARER
        sess.headers.update({
            "User-Agent":                settings.USER_AGENT,
            "Accept":                    "*/*",
            "Accept-Language":           "en-US,en;q=0.9",
            "Authorization":             f"Bearer {bearer}",
            "X-Csrf-Token":              ct0,
            "X-Twitter-Active-User":     "yes",
            "X-Twitter-Auth-Type":       "OAuth2Session",
            "X-Twitter-Client-Language": "en",
            "Content-Type":              "application/json",
            "Origin":                    "https://x.com",
            "Referer":                   "https://x.com/",
        })
        self.session = sess

    def close(self):
        try:
            if self.session:
                self.session.close(); self.session = None
            if self.context:
                self.context.close(); self.context = None
            if self.playwright:
                self.playwright.stop(); self.playwright = None
        except Exception:
            pass

    def _enforce_rate_limit(self):
        if self._last_scrape_time <= 0:
            return
        elapsed = time.time() - self._last_scrape_time
        if elapsed < settings.MIN_GAP_SECONDS:
            wait = settings.MIN_GAP_SECONDS - elapsed
            logger.info(f"Rate-limit guard: tunggu {wait:.0f}s")
            time.sleep(wait)

    # ── STRATEGY 1: GraphQL ───────────────────────────────────────────────
    def _fetch_via_graphql(self, username: str) -> Optional[Dict]:
        if not self.session:
            return None
        op = self.endpoints.get("operations", {}).get("UserByScreenName")
        if not op:
            logger.debug("UserByScreenName operation tidak ada di endpoints")
            return None

        query_id = op.get("query_id", "")
        feats    = op.get("features_encoded", "")
        variables = {"screen_name": username, "withSafetyModeUserFields": True}
        url    = f"https://x.com/i/api/graphql/{query_id}/UserByScreenName"
        params = {"variables": json.dumps(variables, separators=(",", ":"))}
        if feats:
            params["features"] = unquote(feats)

        try:
            resp = self.session.get(url, params=params, timeout=20)
            logger.debug(f"GraphQL status: {resp.status_code}")
            if resp.status_code == 429:
                logger.warning("429 Rate limit GraphQL, tunggu 60s")
                time.sleep(60); return None
            if resp.status_code in (401, 403):
                logger.warning(f"{resp.status_code} — session mungkin expired")
                return None
            if resp.status_code != 200:
                logger.debug(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return None
            data = resp.json()
            user_result = data.get("data", {}).get("user", {}).get("result", {})
            if not user_result:
                logger.debug("user_result kosong")
                return None
            return self._parse_graphql_user(user_result)
        except Exception as e:
            logger.error(f"GraphQL error: {e}")
            return None

    def _parse_graphql_user(self, ur: Dict) -> Dict:
        legacy = ur.get("legacy", {}) or {}
        core   = ur.get("core", {}) or {}
        username = core.get("screen_name") or legacy.get("screen_name", "")
        name     = core.get("name") or legacy.get("name", "")
        is_verified = bool(ur.get("is_blue_verified") or legacy.get("verified")
                           or ur.get("verified_type"))
        avatar = legacy.get("profile_image_url_https", "")
        if avatar:
            avatar = avatar.replace("_normal.", "_400x400.")
        return {
            "username":      username,
            "display_name":  name,
            "user_id":       ur.get("rest_id", ""),
            "bio":           legacy.get("description", ""),
            "location":      legacy.get("location", ""),
            "followers":     int(legacy.get("followers_count", 0)),
            "following":     int(legacy.get("friends_count", 0)),
            "tweets":        int(legacy.get("statuses_count", 0)),
            "likes":         int(legacy.get("favourites_count", 0)),
            "listed_count":  int(legacy.get("listed_count", 0)),
            "media_count":   int(legacy.get("media_count", 0) or 0),
            "is_verified":   is_verified,
            "is_private":    bool(legacy.get("protected", False)),
            "avatar_url":    avatar,
            "banner_url":    legacy.get("profile_banner_url", ""),
            "created_at":    legacy.get("created_at", ""),
            "profile_url":   f"https://x.com/{username}" if username else "",
            "method":        "graphql",
        }

    # ── STRATEGY 2: DOM ───────────────────────────────────────────────────
    def _fetch_via_dom(self, username: str) -> Optional[Dict]:
        try:
            url = f"https://x.com/{username}"
            logger.debug(f"[DOM] Navigasi ke {url}")
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(3, 5))

            loaded = False
            for sel in ["[data-testid='primaryColumn']", "[data-testid='UserName']"]:
                try:
                    self.page.wait_for_selector(sel, timeout=10000)
                    loaded = True; break
                except Exception:
                    pass

            if not loaded:
                body = self.page.inner_text("body").lower()
                if any(p in body for p in [
                    "this account doesn't exist", "user not found", "page doesn't exist",
                ]):
                    return None

            # Scroll bertahap — trigger lazy-load stats
            self.page.evaluate("window.scrollBy(0, 400)")
            time.sleep(1.5)
            self.page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)

            data = {
                "username":    username,
                "display_name": "",
                "bio":          "",
                "location":     "",
                "followers":    0,
                "following":    0,
                "tweets":       0,
                "likes":        0,
                "is_verified":  False,
                "avatar_url":   "",
                "profile_url":  f"https://x.com/{username}",
                "method":       "dom",
            }

            # ── Display name ──────────────────────────────────────────────
            try:
                el = self.page.locator("[data-testid='UserName']").first
                if el.count() > 0:
                    for span in el.locator("span").all():
                        t = (span.text_content() or "").strip()
                        if t and not t.startswith("@") and t != username:
                            data["display_name"] = t; break
            except Exception:
                pass

            # ── Bio ───────────────────────────────────────────────────────
            try:
                el = self.page.locator("[data-testid='UserDescription']").first
                if el.count() > 0:
                    data["bio"] = el.inner_text().strip()
            except Exception:
                pass

            # ── Location ──────────────────────────────────────────────────
            try:
                el = self.page.locator("[data-testid='UserLocation']").first
                if el.count() > 0:
                    data["location"] = el.inner_text().strip()
            except Exception:
                pass

            # ── Avatar ────────────────────────────────────────────────────
            try:
                el = self.page.locator("img[src*='pbs.twimg.com/profile_images']").first
                if el.count() > 0:
                    src = el.get_attribute("src") or ""
                    data["avatar_url"] = src.replace("_normal.", "_400x400.").replace("_bigger.", "_400x400.")
            except Exception:
                pass

            # ══════════════════════════════════════════════════════════════
            # ── FOLLOWERS — FIX UTAMA ─────────────────────────────────────
            # Twitter/X pakai 2 format href untuk followers:
            #   Akun biasa   : /username/followers
            #   Akun verified: /username/verified_followers
            # Selector $= (ends-with) tidak match "verified_followers"
            # karena berakhir dengan "verified_followers" bukan "followers"
            # Solusi: coba keduanya secara eksplisit
            # ══════════════════════════════════════════════════════════════
            def _parse_stat_from_el(el) -> int:
                """Ambil angka dari element link stats Twitter."""
                # Cara 1: aria-label  → "1,234 Followers"
                try:
                    aria = el.get_attribute("aria-label") or ""
                    if aria:
                        m = re.search(r'([\d,\.]+[KMBkmb]?)', aria)
                        if m:
                            val = parse_number(m.group(1))
                            if val > 0:
                                return val
                except Exception:
                    pass

                # Cara 2: span pertama yang isinya angka
                try:
                    for span in el.locator("span").all():
                        t = (span.text_content() or "").strip()
                        if re.match(r'^[\d,\.]+[KMBkmb]?$', t):
                            val = parse_number(t)
                            if val > 0:
                                return val
                except Exception:
                    pass

                # Cara 3: inner_text keseluruhan, ambil angka pertama
                try:
                    inner = el.inner_text().strip()
                    m = re.search(r'([\d,\.]+[KMBkmb]?)', inner)
                    if m:
                        val = parse_number(m.group(1))
                        if val > 0:
                            return val
                except Exception:
                    pass

                return 0

            # Followers: coba verified_followers dulu, lalu followers biasa
            followers_selectors = [
                f"a[href='/{username}/verified_followers']",
                f"a[href='/{username}/followers']",
                "a[href$='/verified_followers']",
                "a[href$='/followers']",
            ]
            for sel in followers_selectors:
                try:
                    el = self.page.locator(sel).first
                    if el.count() > 0:
                        val = _parse_stat_from_el(el)
                        if val > 0:
                            data["followers"] = val
                            logger.debug(f"Followers dari selector '{sel}': {val}")
                            break
                except Exception:
                    continue

            # Following
            following_selectors = [
                f"a[href='/{username}/following']",
                "a[href$='/following']",
            ]
            for sel in following_selectors:
                try:
                    el = self.page.locator(sel).first
                    if el.count() > 0:
                        val = _parse_stat_from_el(el)
                        if val > 0:
                            data["following"] = val
                            logger.debug(f"Following dari selector '{sel}': {val}")
                            break
                except Exception:
                    continue

            # ── Fallback JavaScript jika Playwright selector gagal ─────────
            # Scan SEMUA link di halaman, cari yang href-nya mengandung
            # followers/following, lalu ambil angka dari span di dalamnya
            if data["followers"] == 0 or data["following"] == 0:
                try:
                    js_result = self.page.evaluate("""(username) => {
                        const result = {followers: 0, following: 0};
                        const links = Array.from(document.querySelectorAll('a[href]'));

                        for (const link of links) {
                            const href = (link.getAttribute('href') || '').toLowerCase();

                            const isFollowers = href.includes('/followers') ||
                                                href.includes('/verified_followers');
                            const isFollowing = href.includes('/following') &&
                                                !href.includes('/followers');

                            if (!isFollowers && !isFollowing) continue;

                            // Ambil angka dari aria-label
                            const aria = link.getAttribute('aria-label') || '';
                            const ariaMatch = aria.match(/([\d,\.]+[kmb]?)/i);

                            // Ambil angka dari spans di dalam link
                            let spanNum = '';
                            const spans = link.querySelectorAll('span');
                            for (const sp of spans) {
                                const t = sp.innerText ? sp.innerText.trim() : '';
                                if (/^[\d,\.]+[kmb]?$/i.test(t)) {
                                    spanNum = t;
                                    break;
                                }
                            }

                            const rawNum = ariaMatch ? ariaMatch[1] : spanNum;
                            if (!rawNum) continue;

                            // Parse: hapus koma, detect suffix
                            let num = rawNum.toUpperCase().replace(',', '');
                            let val = 0;
                            if (num.endsWith('K')) val = Math.round(parseFloat(num) * 1000);
                            else if (num.endsWith('M')) val = Math.round(parseFloat(num) * 1000000);
                            else if (num.endsWith('B')) val = Math.round(parseFloat(num) * 1000000000);
                            else val = parseInt(num.replace('.', ''), 10);

                            if (isNaN(val) || val <= 0) continue;

                            if (isFollowers && result.followers === 0) result.followers = val;
                            if (isFollowing && result.following === 0) result.following = val;
                        }

                        return result;
                    }""", username)

                    if js_result:
                        if data["followers"] == 0 and js_result.get("followers", 0) > 0:
                            data["followers"] = js_result["followers"]
                            logger.debug(f"Followers dari JS fallback: {js_result['followers']}")
                        if data["following"] == 0 and js_result.get("following", 0) > 0:
                            data["following"] = js_result["following"]
                            logger.debug(f"Following dari JS fallback: {js_result['following']}")
                except Exception as e:
                    logger.debug(f"JS fallback error: {e}")

            # ── Tweets ────────────────────────────────────────────────────
            try:
                body = self.page.inner_text("body")
                patterns = [
                    r'([\d,]+(?:\.\d+)?[KMB]?)\s+[Pp]osts?',
                    r'([\d,]+(?:\.\d+)?[KMB]?)\s+[Tt]weets?',
                ]
                for pat in patterns:
                    m = re.search(pat, body)
                    if m:
                        val = parse_number(m.group(1))
                        if val > 0:
                            data["tweets"] = val
                            break
            except Exception:
                pass

            # ── Log hasil scrape untuk debugging ─────────────────────────
            logger.info(
                f"[DOM] @{username} → "
                f"followers={data['followers']}, following={data['following']}, "
                f"tweets={data['tweets']}, display_name='{data['display_name']}'"
            )

            # Return kalau minimal ada display_name (followers bisa 0 untuk akun tertentu)
            if data["display_name"] or data["followers"] > 0 or data["following"] > 0:
                return data
            return None

        except Exception as e:
            logger.error(f"DOM strategy error: {e}")
            return None

    # ── STRATEGY 3: HTML Meta ─────────────────────────────────────────────
    def _fetch_via_html(self, username: str) -> Optional[Dict]:
        try:
            content = self.page.content()
            display_name = bio = avatar = ""
            tm = re.search(r'<title[^>]*>([^<]+)</title>', content)
            if tm:
                nm = re.search(r'^([^(]+)', tm.group(1))
                if nm:
                    display_name = nm.group(1).strip()
            dm = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', content)
            if dm:
                bio = dm.group(1)
            im = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', content)
            if im:
                avatar = im.group(1)

            followers = following = tweets = 0
            fm = re.search(r'([\d,]+(?:\.\d+)?[KMB]?)\s+Followers', content, re.IGNORECASE)
            if fm: followers = parse_number(fm.group(1))
            fgm = re.search(r'([\d,]+(?:\.\d+)?[KMB]?)\s+Following', content, re.IGNORECASE)
            if fgm: following = parse_number(fgm.group(1))
            tmt = re.search(r'([\d,]+(?:\.\d+)?[KMB]?)\s+(?:Posts?|Tweets?)', content, re.IGNORECASE)
            if tmt: tweets = parse_number(tmt.group(1))

            if followers > 0 or display_name:
                return {
                    "username": username, "display_name": display_name, "bio": bio,
                    "followers": followers, "following": following, "tweets": tweets,
                    "likes": 0, "is_verified": False, "avatar_url": avatar,
                    "profile_url": f"https://x.com/{username}", "method": "html_meta",
                }
            return None
        except Exception as e:
            logger.error(f"HTML meta error: {e}")
            return None

    # ── MAIN SCRAPE ───────────────────────────────────────────────────────
    def scrape_profile(self, username_or_url: str) -> Dict:
        try:
            username = parse_username_from_input(username_or_url)
        except ValueError as e:
            return {"success": False, "username": username_or_url,
                    "scraped_at": datetime.now().isoformat(), "data": {}, "error": str(e)}

        logger.info(f"Scraping @{username}")
        result = {"success": False, "username": username,
                  "scraped_at": datetime.now().isoformat(), "data": {}, "error": None}

        try:
            self.initialize_browser()
            self._enforce_rate_limit()
            profile_data = None

            # Strategy 1
            if self.session and self.endpoints.get("operations", {}).get("UserByScreenName"):
                logger.debug("[Strategy 1] GraphQL")
                profile_data = self._fetch_via_graphql(username)
                if profile_data:
                    logger.info("Berhasil via GraphQL")

            # Strategy 2
            if not profile_data:
                logger.debug("[Strategy 2] DOM")
                profile_data = self._fetch_via_dom(username)
                if profile_data:
                    logger.info("Berhasil via DOM")

            # Strategy 3
            if not profile_data:
                logger.debug("[Strategy 3] HTML meta")
                profile_data = self._fetch_via_html(username)
                if profile_data:
                    logger.info("Berhasil via HTML meta")

            if not profile_data:
                raise Exception(
                    f"Semua strategy gagal untuk @{username} "
                    "(user tidak ada / private / rate limit)"
                )

            profile_data["username"]   = username
            profile_data["scraped_at"] = datetime.now().isoformat()
            result["success"] = True
            result["data"]    = profile_data
        except Exception as e:
            logger.error(f"GAGAL scrape @{username}: {e}")
            result["error"] = str(e)

        self._last_scrape_time = time.time()
        return result
"""
tweet_scraper.py
================
Twitter/X TWEET / POST Scraper — GraphQL based.

Tiga mode:
  1. scrape_user_tweets(username)   → timeline tweet milik 1 user
  2. scrape_tweet_replies(url)      → 1 tweet + balasannya (sort newest/oldest/likes)
  3. scrape_search(query)           → hasil pencarian / hashtag

Auth: cookie-based via app.core.cookie_injector (sama seperti profile_scraper).
Reuse pola: persistent context + inject cookies + requests.Session + rate-limit guard.

Sentiment analysis OPSIONAL — kalau modul sentiment_analyzer_v2 tersedia di
working dir, otomatis dipakai; kalau tidak, di-skip tanpa error.

─────────────────────────────────────────────────────────────────────────────
PERUBAHAN:
  ─ scrape_search   → BROWSER NETWORK CAPTURE (utama) + GraphQL requests (fallback)
  ─ scrape_tweet_replies → DIROMBAK dengan pola yang sama:
      • _replies_via_browser  : buka halaman tweet, intercept response
        GraphQL "TweetDetail" dari network, scroll untuk narik balasan.
      • _replies_via_graphql  : jalur lama (requests + TweetDetail dari
        twitter_endpoints.json) dipakai sebagai FALLBACK kalau browser
        capture kosong.
    Ini menyembuhkan error "Tidak ada data (cek endpoints/sesi)" yang muncul
    saat operasi TweetDetail di endpoints stale / queryId dirotate X.
  ─ Bonus: navigasi ke halaman tweet juga memicu request TweetDetail, sehingga
    endpoint_capturer.py (kalau aktif di browser yang sama) bisa menangkap
    operasinya untuk dipakai lain kali.
─────────────────────────────────────────────────────────────────────────────
"""
import os
import re
import json
import time
import random
import requests
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from collections import Counter
from urllib.parse import unquote, quote

from playwright.sync_api import sync_playwright, Page, BrowserContext

from app.core.config import settings
from app.core.logger import get_logger
from app.core import cookie_injector as ci

logger = get_logger("tweet_scraper")

ENDPOINTS_FILE = os.path.join(os.getcwd(), "twitter_endpoints.json")

# Sentiment opsional — tidak wajib ada
try:
    from sentiment_analyzer_v2 import SentimentAnalyzerV2  # type: ignore
    SENTIMENT_AVAILABLE = True
except Exception:
    SENTIMENT_AVAILABLE = False


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _twitter_date_to_epoch(date_str: str) -> int:
    if not date_str:
        return 0
    try:
        return int(parsedate_to_datetime(date_str).timestamp())
    except Exception:
        try:
            dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
            return int(dt.timestamp())
        except Exception:
            return 0


def parse_username_from_input(raw: str) -> str:
    """Terima '@user', 'user', atau URL profil → kembalikan 'user'."""
    raw = (raw or "").strip()
    if raw.startswith("@"):
        return raw[1:]
    if "x.com/" in raw or "twitter.com/" in raw:
        m = re.search(r"(?:x|twitter)\.com/([^/?#]+)", raw)
        if m:
            return m.group(1)
    return raw


# ── MAIN CLASS ───────────────────────────────────────────────────────────────

class TwitterTweetScraper:
    """
    Scraper post/tweet. Dipakai dengan context manager:

        with TwitterTweetScraper() as s:
            data = s.scrape_user_tweets("nasa", max_tweets=50)
    """

    def __init__(self, sentiment_mode: Optional[str] = None):
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.session: Optional[requests.Session] = None
        self.playwright = None
        self._last_scrape_time: float = 0.0
        self.endpoints: Dict = {}
        self._load_endpoints()

        # Sentiment opsional
        self.sentiment = None
        if SENTIMENT_AVAILABLE and sentiment_mode:
            try:
                self.sentiment = SentimentAnalyzerV2(mode=sentiment_mode, verbose=False)
                logger.info(f"Sentiment analyzer aktif (mode={sentiment_mode})")
            except Exception as e:
                logger.warning(f"Sentiment gagal di-load, di-skip: {e}")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── ENDPOINTS ─────────────────────────────────────────────────────────
    def _load_endpoints(self):
        if not os.path.exists(ENDPOINTS_FILE):
            logger.warning(f"{ENDPOINTS_FILE} tidak ada — GraphQL operations kosong")
            self.endpoints = {"bearer_token": settings.FALLBACK_BEARER, "operations": {}}
            return
        try:
            with open(ENDPOINTS_FILE, "r", encoding="utf-8") as f:
                self.endpoints = json.load(f)
            if not self.endpoints.get("bearer_token"):
                self.endpoints["bearer_token"] = settings.FALLBACK_BEARER
            ops = self.endpoints.get("operations", {})
            logger.info(f"Endpoints loaded: {len(ops)} operasi")
        except Exception as e:
            logger.error(f"Gagal baca endpoints: {e}")
            self.endpoints = {"bearer_token": settings.FALLBACK_BEARER, "operations": {}}

    # ── BROWSER + SESSION (mirror profile_scraper) ────────────────────────
    def _build_context(self):
        self.playwright = sync_playwright().start()
        stealth = """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
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
        logger.info("Membuka browser Playwright (tweet scraper)...")
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

    # ── GRAPHQL CORE ──────────────────────────────────────────────────────
    def _build_variables(self, op_name: str, overrides: Dict) -> Dict:
        op_cfg = self.endpoints.get("operations", {}).get(op_name, {})
        enc = op_cfg.get("variables_encoded", "")
        original = {}
        if enc:
            try:
                original = json.loads(unquote(enc))
            except Exception:
                original = {}
        return {**original, **overrides}

    def _graphql_get(self, op_name: str, overrides: Dict) -> Optional[Dict]:
        if not self.session:
            return None
        op = self.endpoints.get("operations", {}).get(op_name)
        if not op:
            logger.warning(f"Operasi '{op_name}' belum ada di twitter_endpoints.json")
            return None

        query_id = op.get("query_id", "")
        feats    = op.get("features_encoded", "")
        variables = self._build_variables(op_name, overrides)
        url    = f"https://x.com/i/api/graphql/{query_id}/{op_name}"
        params = {"variables": json.dumps(variables, separators=(",", ":"))}
        if feats:
            params["features"] = unquote(feats)

        try:
            resp = self.session.get(url, params=params, timeout=25)
            logger.debug(f"GraphQL {op_name}: {resp.status_code}")
            if resp.status_code == 429:
                logger.warning("429 Rate limit — tunggu 60s"); time.sleep(60); return None
            if resp.status_code in (401, 403):
                logger.warning(f"{resp.status_code} — session mungkin expired"); return None
            if resp.status_code == 404:
                logger.warning("404 — queryId mungkin expired, refresh endpoints"); return None
            if resp.status_code != 200:
                logger.debug(f"HTTP {resp.status_code}: {resp.text[:200]}"); return None
            if "json" not in resp.headers.get("content-type", ""):
                return None
            data = resp.json()
            if data.get("errors"):
                logger.warning(f"GraphQL error: {str(data['errors'][0].get('message',''))[:150]}")
            return data
        except Exception as e:
            logger.error(f"GraphQL exception ({op_name}): {e}")
            return None

    # ── PARSERS ───────────────────────────────────────────────────────────
    def _deep_get(self, d: Dict, paths: List[str], default=None):
        for path in paths:
            try:
                cur = d
                for key in path.split("."):
                    m = re.match(r"^(.+)\[(\d+)\]$", key)
                    if m:
                        cur = cur[m.group(1)][int(m.group(2))]
                    else:
                        cur = cur[key]
                if cur is not None:
                    return cur
            except (KeyError, TypeError, IndexError):
                continue
        return default

    def _parse_tweet(self, tweet_result: Dict) -> Optional[Dict]:
        if not tweet_result:
            return None
        result = tweet_result
        if result.get("__typename") == "TweetWithVisibilityResults":
            result = result.get("tweet", {})
        if isinstance(result.get("tweet"), dict):
            inner = result["tweet"]
            if "legacy" in inner or "core" in inner:
                result = inner

        legacy  = result.get("legacy", {}) or {}
        views   = result.get("views",  {}) or {}
        note_tw = result.get("note_tweet", {}) or {}

        tweet_id = result.get("rest_id") or legacy.get("id_str", "")
        if not tweet_id:
            return None

        full_text = (
            self._deep_get(note_tw, ["note_tweet_results.result.text"], "")
            if note_tw else legacy.get("full_text", "")
        )

        user_result = self._deep_get(result, [
            "core.user_results.result", "core.user", "user_results.result",
        ], {}) or {}
        user_legacy = user_result.get("legacy", {}) or {}
        user_core   = user_result.get("core",   {}) or {}
        username    = user_core.get("screen_name") or user_legacy.get("screen_name", "")
        name        = user_core.get("name")        or user_legacy.get("name", "")
        is_verified = bool(
            user_result.get("is_blue_verified", False)
            or user_legacy.get("verified", False)
            or user_result.get("verified_type")
        )

        media_list = []
        for m in (legacy.get("extended_entities", {}) or {}).get("media", []):
            mi = {"type": m.get("type", "photo"), "url": m.get("media_url_https", "")}
            if m.get("type") in ["video", "animated_gif"]:
                variants = (m.get("video_info", {}) or {}).get("variants", [])
                mp4 = [v for v in variants if v.get("content_type") == "video/mp4"]
                if mp4:
                    best = max(mp4, key=lambda v: v.get("bitrate", 0))
                    mi["video_url"] = best.get("url", "")
            media_list.append(mi)

        entities = legacy.get("entities", {}) or {}
        hashtags = [h["text"] for h in entities.get("hashtags", []) if h.get("text")]
        mentions = [u["screen_name"] for u in entities.get("user_mentions", []) if u.get("screen_name")]
        urls     = [u.get("expanded_url", "") for u in entities.get("urls", []) if u.get("expanded_url")]

        created_at_str = legacy.get("created_at", "")
        return {
            "tweet_id":       tweet_id,
            "url":            f"https://x.com/{username}/status/{tweet_id}" if username else "",
            "text":           full_text,
            "created_at":     created_at_str,
            "created_at_epoch": _twitter_date_to_epoch(created_at_str),
            "lang":           legacy.get("lang", ""),
            "like_count":     int(legacy.get("favorite_count", 0)),
            "retweet_count":  int(legacy.get("retweet_count", 0)),
            "reply_count":    int(legacy.get("reply_count", 0)),
            "quote_count":    int(legacy.get("quote_count", 0)),
            "bookmark_count": int(legacy.get("bookmark_count", 0)),
            "view_count":     int(views.get("count", 0) or 0),
            "user": {
                "username":        username,
                "name":            name,
                "verified":        is_verified,
                "followers_count": int(user_legacy.get("followers_count", 0)),
                "profile_image":   user_legacy.get("profile_image_url_https", ""),
            },
            "media":          media_list,
            "hashtags":       hashtags,
            "mentions":       mentions,
            "urls":           urls,
            "is_reply":       bool(legacy.get("in_reply_to_status_id_str", "")),
            "is_retweet":     "retweeted_status_result" in result,
        }

    def _extract_tweet_entries(self, instructions: List[Dict]) -> List[Dict]:
        tweets = []
        for inst in instructions:
            itype = inst.get("type", "")
            if itype not in ["TimelineAddEntries", "TimelineReplaceEntry", "TimelinePinEntry"]:
                continue
            entries = [inst.get("entry", {})] if itype == "TimelinePinEntry" else inst.get("entries", [])
            for entry in entries:
                content = entry.get("content", {}) or entry.get("item", {}).get("content", {})
                etype = content.get("entryType", "")
                if etype == "TimelineTimelineItem":
                    ic = content.get("itemContent", {})
                    if ic.get("itemType") == "TimelineTweet":
                        tw = self._parse_tweet(self._deep_get(ic, ["tweet_results.result"], {}))
                        if tw:
                            tweets.append(tw)
                elif etype == "TimelineTimelineModule":
                    for item in content.get("items", []):
                        ic = item.get("item", {}).get("itemContent", {})
                        if ic.get("itemType") == "TimelineTweet":
                            tw = self._parse_tweet(self._deep_get(ic, ["tweet_results.result"], {}))
                            if tw:
                                tweets.append(tw)
        return tweets

    def _extract_cursor(self, instructions: List[Dict], cursor_type: str = "Bottom") -> Optional[str]:
        for inst in instructions:
            if inst.get("type") not in ["TimelineAddEntries", "TimelineReplaceEntry"]:
                continue
            for entry in inst.get("entries", []):
                content = entry.get("content", {})
                if content.get("entryType") == "TimelineTimelineCursor" \
                        and content.get("cursorType") == cursor_type:
                    return content.get("value")
                if content.get("entryType") == "TimelineTimelineModule":
                    for item in content.get("items", []):
                        ic = item.get("item", {}).get("itemContent", {})
                        if ic.get("itemType") == "TimelineTimelineCursor" \
                                and ic.get("cursorType") == cursor_type:
                            return ic.get("value")
        return None

    def _extract_instructions(self, data: Dict, response_type: str) -> List[Dict]:
        if not data:
            return []
        d = data.get("data", {}) or {}
        paths = {
            "tweet_detail": [
                "threaded_conversation_with_injections_v2.instructions",
                "threaded_conversation_with_injections.instructions",
            ],
            "user_tweets": [
                "user.result.timeline.timeline.instructions",
                "user.result.timeline_v2.timeline.instructions",
                "user.result.timeline_response.timeline.instructions",
            ],
            "search": [
                "search_by_raw_query.search_timeline.timeline.instructions",
                "search_by_raw_query.search_timeline_v2.timeline.instructions",
            ],
        }
        return self._deep_get(d, paths.get(response_type, []), []) or []

    def _sort_replies(self, replies: List[Dict], sort_by: str = "newest") -> List[Dict]:
        if sort_by == "newest":
            return sorted(replies, key=lambda x: x.get("created_at_epoch", 0), reverse=True)
        if sort_by == "oldest":
            return sorted(replies, key=lambda x: x.get("created_at_epoch", 0))
        if sort_by == "likes":
            return sorted(replies, key=lambda x: x.get("like_count", 0), reverse=True)
        return replies

    def _maybe_sentiment(self, tweets: List[Dict]) -> List[Dict]:
        if not self.sentiment or not tweets:
            return tweets
        for tw in tweets:
            text = tw.get("text", "")
            if not text:
                continue
            try:
                a = self.sentiment.analyze_sentiment(text)   # cukup 1x
                tw["sentiment"]      = a.get("sentiment", "")
                tw["is_hate_speech"] = a.get("is_hate_speech", False)
                tw["is_toxic"]       = a.get("is_toxic", False)
                # Derive kategori dari hasil analisis — tanpa analyze ulang
                if a.get("is_hate_speech"):
                    tw["category"] = "HATE_SPEECH"
                elif a.get("is_toxic"):
                    tw["category"] = "TOXIC"
                elif a.get("sentiment") == "POSITIVE":
                    tw["category"] = "POSITIVE"
                elif a.get("sentiment") == "NEGATIVE":
                    tw["category"] = "NEGATIVE"
                elif a.get("humor_words"):
                    tw["category"] = "HUMOR"
                else:
                    tw["category"] = "NEUTRAL"
            except Exception as e:
                logger.debug(f"Sentiment skip: {e}")
        return tweets

    def _summarize(self, tweets: List[Dict], mode: str = "tweets") -> Dict:
            if not tweets:
                return {"total": 0, "top_5_by_likes": []}

            total        = len(tweets)
            top_hashtags = Counter([h.lower() for t in tweets for h in t.get("hashtags", [])])

            # Top 5 by likes
            with_likes = [t for t in tweets if t.get("like_count", 0) > 0]
            top5 = sorted(with_likes, key=lambda x: x.get("like_count", 0), reverse=True)[:5]
            top_5_by_likes = [
                {
                    "rank":          i + 1,
                    "tweet_id":      t.get("tweet_id", ""),
                    "url":           t.get("url", ""),
                    "text":          t.get("text", ""),
                    "like_count":    t.get("like_count", 0),
                    "retweet_count": t.get("retweet_count", 0),
                    "reply_count":   t.get("reply_count", 0),
                    "view_count":    t.get("view_count", 0),
                    "created_at":    t.get("created_at", ""),
                    "user": {
                        "username":      t.get("user", {}).get("username", ""),
                        "name":          t.get("user", {}).get("name", ""),
                        "verified":      t.get("user", {}).get("verified", False),
                        "profile_image": t.get("user", {}).get("profile_image", ""),
                    },
                    "category":  t.get("category", ""),
                    "sentiment": t.get("sentiment", ""),
                }
                for i, t in enumerate(top5)
            ]

            s = {
                "total": total,
                "top_5_by_likes": top_5_by_likes,
                "engagement_total": {
                    "likes":    sum(t.get("like_count",    0) for t in tweets),
                    "retweets": sum(t.get("retweet_count", 0) for t in tweets),
                    "replies":  sum(t.get("reply_count",   0) for t in tweets),
                    "views":    sum(t.get("view_count",    0) for t in tweets),
                },
                "engagement_avg": {
                    "likes":    round(sum(t.get("like_count",    0) for t in tweets) / total, 1),
                    "retweets": round(sum(t.get("retweet_count", 0) for t in tweets) / total, 1),
                    "views":    round(sum(t.get("view_count",    0) for t in tweets) / total, 1),
                },
                "top_hashtags": top_hashtags.most_common(10),
            }

            if self.sentiment:
                counts = Counter(t.get("category", "NEUTRAL") for t in tweets)
                s["sentiment_breakdown"] = dict(counts)

            return s

    # ── MODE 1: USER TWEETS ───────────────────────────────────────────────
    def scrape_user_tweets(self, username: str, max_tweets: int = 40) -> Dict:
        username = parse_username_from_input(username)
        logger.info(f"Scrape user tweets: @{username} (max {max_tweets})")
        out = {
            "success": False, "mode": "user_tweets", "username": username,
            "scraped_at": datetime.now().isoformat(),
            "user_info": {}, "tweets": [], "tweets_count": 0, "summary": {},
        }
        try:
            self.initialize_browser()
            self._enforce_rate_limit()

            user_data = self._graphql_get("UserByScreenName", {"screen_name": username})
            if not user_data:
                out["error"] = "Gagal resolve user (cek endpoints/sesi)"; return out
            ur = self._deep_get(user_data, ["data.user.result"], {}) or {}
            user_id = ur.get("rest_id", "")
            ul = ur.get("legacy", {}) or {}
            uc = ur.get("core", {}) or {}
            out["user_info"] = {
                "user_id": user_id,
                "username": username,
                "name": uc.get("name") or ul.get("name", ""),
                "followers_count": int(ul.get("followers_count", 0)),
                "following_count": int(ul.get("friends_count", 0)),
                "tweet_count": int(ul.get("statuses_count", 0)),
            }
            if not user_id:
                out["error"] = "user_id kosong / user tidak ditemukan"; return out

            all_tweets, cursor, page = [], None, 0
            while len(all_tweets) < max_tweets and page < 30:
                page += 1
                ov = {"userId": user_id, "count": 40}
                if cursor:
                    ov["cursor"] = cursor
                data = self._graphql_get("UserTweets", ov)
                if not data:
                    break
                inst = self._extract_instructions(data, "user_tweets")
                if not inst:
                    break
                page_tweets = self._extract_tweet_entries(inst)
                if not page_tweets:
                    break
                ids = {t["tweet_id"] for t in all_tweets}
                all_tweets.extend([t for t in page_tweets if t["tweet_id"] not in ids])
                logger.debug(f"Page {page}: total {len(all_tweets)}")
                nxt = self._extract_cursor(inst, "Bottom")
                if not nxt or nxt == cursor:
                    break
                cursor = nxt
                time.sleep(random.uniform(2.0, 3.5))

            all_tweets = sorted(all_tweets, key=lambda x: x.get("created_at_epoch", 0), reverse=True)[:max_tweets]
            all_tweets = self._maybe_sentiment(all_tweets)
            out["tweets"] = all_tweets
            out["tweets_count"] = len(all_tweets)
            out["summary"] = self._summarize(all_tweets)
            out["success"] = True
        except Exception as e:
            logger.error(f"scrape_user_tweets gagal: {e}")
            out["error"] = str(e)
        self._last_scrape_time = time.time()
        return out

    # ══════════════════════════════════════════════════════════════════════
    # MODE 2: TWEET + REPLIES  (REWRITTEN — browser capture utama)
    # ══════════════════════════════════════════════════════════════════════
    def scrape_tweet_replies(self, tweet_url: str, max_replies: int = 50,
                             sort_by: str = "newest") -> Dict:
        """
        Ambil 1 tweet + balasannya.

        sort_by: "newest" | "oldest" | "likes" (di-sort di sisi Python).

        Strategi:
          1. BROWSER CAPTURE (utama) — buka halaman tweet, intercept response
             GraphQL TweetDetail dari network. Tahan banting karena tidak
             bergantung pada queryId/features hasil capture.
          2. GRAPHQL REQUESTS (fallback) — pakai operasi TweetDetail dari
             twitter_endpoints.json kalau ada.
        """
        m = re.search(r"/status/(\d+)", tweet_url)
        out = {
            "success": False, "mode": "tweet_replies", "url": tweet_url,
            "scraped_at": datetime.now().isoformat(), "sort_by": sort_by,
            "method": "", "focal_tweet": {}, "replies": [], "replies_count": 0,
            "summary": {},
        }
        if not m:
            out["error"] = "URL tidak valid — harus mengandung /status/<id>"; return out
        focal_id = m.group(1)
        out["tweet_id"] = focal_id
        logger.info(f"Scrape tweet replies: {focal_id} (max {max_replies}, sort {sort_by})")
        try:
            self.initialize_browser()
            self._enforce_rate_limit()

            # ── Strategy 1: Browser network capture ──
            all_tweets = self._replies_via_browser(tweet_url, focal_id, max_replies)
            method = "browser_capture"

            # ── Strategy 2: GraphQL requests fallback ──
            if not all_tweets:
                logger.warning("Browser capture kosong — fallback ke GraphQL requests")
                all_tweets = self._replies_via_graphql(focal_id, max_replies)
                method = "graphql_requests"

            if not all_tweets:
                out["error"] = "Tidak ada data (cek endpoints/sesi)"; return out

            focal = next((t for t in all_tweets if t["tweet_id"] == focal_id), None)
            raw_replies = [t for t in all_tweets if t["tweet_id"] != focal_id]
            replies = self._sort_replies(raw_replies, sort_by)[:max_replies]
            replies = self._maybe_sentiment(replies)

            out["focal_tweet"]   = focal or {}
            out["replies"]       = replies
            out["replies_count"] = len(replies)
            out["summary"]       = self._summarize(replies)
            out["method"]        = method
            out["success"]       = True
            logger.info(f"Replies {focal_id}: {len(replies)} balasan via {method}")
        except Exception as e:
            logger.error(f"scrape_tweet_replies gagal: {e}")
            out["error"] = str(e)
        self._last_scrape_time = time.time()
        return out

    # ── Strategy 1: tangkap TweetDetail dari network browser ──────────────
    def _replies_via_browser(self, tweet_url: str, focal_id: str,
                             max_replies: int) -> List[Dict]:
        page = self.page
        if page is None:
            return []

        captured: List[Dict] = []

        def _on_response(response):
            # Hanya tangkap response GraphQL TweetDetail
            try:
                if "TweetDetail" not in response.url:
                    return
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    return
                captured.append(response.json())
            except Exception:
                # Body bisa saja belum tersedia / redirect — abaikan
                pass

        page.on("response", _on_response)

        # Normalisasi URL ke x.com (kalau user paste twitter.com)
        url = (tweet_url or "").replace("twitter.com", "x.com")
        if not url.startswith("http"):
            url = f"https://x.com/i/status/{focal_id}"

        all_tweets: List[Dict] = []
        seen: set = set()

        def _drain() -> int:
            """Proses semua response yang sudah ke-capture → tweet baru."""
            added = 0
            while captured:
                data = captured.pop(0)
                inst = self._extract_instructions(data, "tweet_detail")
                for tw in self._extract_tweet_entries(inst):
                    tid = tw.get("tweet_id")
                    if tid and tid not in seen:
                        seen.add(tid)
                        all_tweets.append(tw)
                        added += 1
            return added

        # Target sengaja dilebihkan agar focal + cukup banyak balasan tertangkap
        target = max(max_replies + 5, int(max_replies * 1.5)) + 1

        try:
            logger.info(f"Buka halaman tweet: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Cek redirect ke login (sesi mati)
            if "login" in page.url or "/i/flow" in page.url:
                logger.error("Tweet detail redirect ke login — sesi expired")
                return []

            # Tunggu batch pertama (maks ~15 detik)
            for _ in range(15):
                time.sleep(1.0)
                _drain()
                if all_tweets:
                    break

            # Scroll untuk narik balasan tambahan
            stall = 0
            last = len(all_tweets)
            for i in range(60):
                if len(all_tweets) >= target:
                    break
                try:
                    page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                except Exception:
                    pass
                time.sleep(random.uniform(1.8, 3.0))
                _drain()
                logger.debug(f"Scroll {i+1}: total {len(all_tweets)}")

                if len(all_tweets) == last:
                    stall += 1
                    if stall >= 5:   # 5x scroll tanpa tambahan → mentok
                        logger.debug("Scroll mentok — stop")
                        break
                else:
                    stall = 0
                last = len(all_tweets)

            # Drain terakhir
            time.sleep(1.5)
            _drain()

        except Exception as e:
            logger.warning(f"Browser tweet-detail error: {e}")
        finally:
            try:
                page.remove_listener("response", _on_response)
            except Exception:
                pass

        logger.info(f"Browser capture: {len(all_tweets)} tweet (termasuk focal) untuk {focal_id}")
        return all_tweets

    # ── Strategy 2: TweetDetail via requests (butuh endpoints) ────────────
    def _replies_via_graphql(self, focal_id: str, max_replies: int) -> List[Dict]:
        all_tweets: List[Dict] = []
        cursor, page = None, 0
        target = max(max_replies + 10, int(max_replies * 1.5))
        while len(all_tweets) < target + 1 and page < 30:
            page += 1
            ov = {"focalTweetId": focal_id, "rankingMode": "Recency"}
            if cursor:
                ov["cursor"] = cursor
                ov["referrer"] = "tweet"
            data = self._graphql_get("TweetDetail", ov)
            if not data:
                break
            inst = self._extract_instructions(data, "tweet_detail")
            if not inst:
                break
            page_tweets = self._extract_tweet_entries(inst)
            if not page_tweets:
                break
            ids = {t["tweet_id"] for t in all_tweets}
            all_tweets.extend([t for t in page_tweets if t["tweet_id"] not in ids])
            nxt = self._extract_cursor(inst, "Bottom")
            if not nxt or nxt == cursor:
                break
            cursor = nxt
            time.sleep(random.uniform(2.0, 3.5))
        return all_tweets

    # ══════════════════════════════════════════════════════════════════════
    # MODE 3: SEARCH / HASHTAG  (browser capture utama)
    # ══════════════════════════════════════════════════════════════════════
    def scrape_search(self, query: str, max_tweets: int = 40,
                      search_type: str = "Latest") -> Dict:
        """
        Search / hashtag scraper.

        search_type: "Latest" | "Top" | "Media" | "People"
          → "Latest" memetakan ke filter live (f=live).
          → query bisa berupa keyword ("makanan bergizi") atau hashtag ("#sampah").

        Strategi:
          1. BROWSER CAPTURE (utama) — buka x.com/search lalu intercept
             response GraphQL SearchTimeline langsung dari network.
          2. GRAPHQL REQUESTS (fallback) — pakai operasi SearchTimeline dari
             twitter_endpoints.json kalau ada.
        """
        logger.info(f"Scrape search: '{query}' ({search_type}, max {max_tweets})")
        out = {
            "success": False, "mode": "search", "query": query,
            "search_type": search_type, "scraped_at": datetime.now().isoformat(),
            "method": "", "tweets": [], "tweets_count": 0, "summary": {},
        }
        try:
            self.initialize_browser()
            self._enforce_rate_limit()

            # ── Strategy 1: Browser network capture ──
            tweets = self._search_via_browser(query, max_tweets, search_type)
            method = "browser_capture"

            # ── Strategy 2: GraphQL requests fallback ──
            if not tweets:
                logger.warning("Browser capture kosong — fallback ke GraphQL requests")
                tweets = self._search_via_graphql(query, max_tweets, search_type)
                method = "graphql_requests"

            # Sort sesuai tipe
            if search_type == "Latest":
                tweets = sorted(tweets, key=lambda x: x.get("created_at_epoch", 0), reverse=True)
            elif search_type == "Top":
                tweets = sorted(tweets, key=lambda x: x.get("like_count", 0), reverse=True)
            tweets = tweets[:max_tweets]
            tweets = self._maybe_sentiment(tweets)

            out["tweets"]       = tweets
            out["tweets_count"] = len(tweets)
            out["summary"]      = self._summarize(tweets)
            out["method"]       = method if tweets else ""
            out["success"]      = True
            logger.info(f"Search '{query}': {len(tweets)} tweet via {out['method'] or '-'}")
        except Exception as e:
            logger.error(f"scrape_search gagal: {e}")
            out["error"] = str(e)
        self._last_scrape_time = time.time()
        return out

    # ── Strategy 1: tangkap SearchTimeline dari network browser ───────────
    def _search_via_browser(self, query: str, max_tweets: int,
                            search_type: str) -> List[Dict]:
        page = self.page
        if page is None:
            return []

        captured: List[Dict] = []

        def _on_response(response):
            # Hanya tangkap response GraphQL SearchTimeline
            try:
                if "SearchTimeline" not in response.url:
                    return
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    return
                captured.append(response.json())
            except Exception:
                # Body bisa saja belum tersedia / redirect — abaikan
                pass

        page.on("response", _on_response)

        # Map tipe → filter URL X
        #   Latest → live | Top → (default) | Media → media | People → user
        f_map = {"Latest": "live", "Top": "", "Media": "media", "People": "user"}
        f_param = f_map.get(search_type, "live")
        url = f"https://x.com/search?q={quote(query)}&src=typed_query"
        if f_param:
            url += f"&f={f_param}"

        all_tweets: List[Dict] = []
        seen: set = set()

        def _drain() -> int:
            """Proses semua response yang sudah ke-capture → tweet baru."""
            added = 0
            while captured:
                data = captured.pop(0)
                inst = self._extract_instructions(data, "search")
                for tw in self._extract_tweet_entries(inst):
                    tid = tw.get("tweet_id")
                    if tid and tid not in seen:
                        seen.add(tid)
                        all_tweets.append(tw)
                        added += 1
            return added

        try:
            logger.info(f"Buka halaman search: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Cek redirect ke login (sesi mati)
            if "login" in page.url or "/i/flow" in page.url:
                logger.error("Search redirect ke login — sesi expired")
                return []

            # Tunggu batch pertama (maks ~15 detik)
            for _ in range(15):
                time.sleep(1.0)
                _drain()
                if all_tweets:
                    break

            # Scroll untuk paginasi
            stall = 0
            last = len(all_tweets)
            for i in range(60):
                if len(all_tweets) >= max_tweets:
                    break
                try:
                    page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                except Exception:
                    pass
                time.sleep(random.uniform(1.8, 3.0))
                _drain()
                logger.debug(f"Scroll {i+1}: total {len(all_tweets)}")

                if len(all_tweets) == last:
                    stall += 1
                    if stall >= 5:   # 5x scroll tanpa tambahan → mentok
                        logger.debug("Scroll mentok — stop")
                        break
                else:
                    stall = 0
                last = len(all_tweets)

            # Drain terakhir
            time.sleep(1.5)
            _drain()

        except Exception as e:
            logger.warning(f"Browser search error: {e}")
        finally:
            try:
                page.remove_listener("response", _on_response)
            except Exception:
                pass

        logger.info(f"Browser capture: {len(all_tweets)} tweet untuk '{query}'")
        return all_tweets

    # ── Strategy 2: SearchTimeline via requests (butuh endpoints) ─────────
    def _search_via_graphql(self, query: str, max_tweets: int,
                           search_type: str) -> List[Dict]:
        all_tweets: List[Dict] = []
        seen: set = set()
        cursor, page = None, 0
        while len(all_tweets) < max_tweets and page < 30:
            page += 1
            ov = {"rawQuery": query, "count": 20,
                  "querySource": "typed_query", "product": search_type}
            if cursor:
                ov["cursor"] = cursor
            data = self._graphql_get("SearchTimeline", ov)
            if not data:
                break
            inst = self._extract_instructions(data, "search")
            if not inst:
                break
            page_tweets = self._extract_tweet_entries(inst)
            new = [t for t in page_tweets if t["tweet_id"] not in seen]
            if not new:
                break
            for t in new:
                seen.add(t["tweet_id"])
            all_tweets.extend(new)
            nxt = self._extract_cursor(inst, "Bottom")
            if not nxt or nxt == cursor:
                break
            cursor = nxt
            time.sleep(random.uniform(2.5, 4.0))
        return all_tweets
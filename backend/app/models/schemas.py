"""
schemas.py — Semua Pydantic request models untuk seluruh router.

Router yang memakai file ini:
  - auth.py      → CookieImportRequest, LoginBrowserRequest, LogoutRequest
  - scrape.py    → ScrapeProfileRequest, BatchScrapeRequest
  - profiles.py  → ManualTrackRequest
  - tweets.py    → ScrapeUserTweetsRequest, ScrapeRepliesRequest, ScrapeSearchRequest
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


# ── Auth ──────────────────────────────────────────────────────────────────────

class CookieImportRequest(BaseModel):
    cookies: List[Dict[str, Any]]
    username: Optional[str] = ""


class LoginBrowserRequest(BaseModel):
    timeout_minutes: int = Field(default=5, ge=1, le=60)
    headless: bool = False


class LogoutRequest(BaseModel):
    hard_reset: bool = False


# ── Scrape profil ─────────────────────────────────────────────────────────────

class ScrapeProfileRequest(BaseModel):
    username: str
    save_tracking: bool = True


class BatchScrapeRequest(BaseModel):
    usernames: List[str]
    delay_between: int = Field(default=12, ge=1)
    save_tracking: bool = True


# ── Growth tracking / profiles ────────────────────────────────────────────────

class ManualTrackRequest(BaseModel):
    username: str
    followers: Optional[int] = None
    following: Optional[int] = None
    tweets: Optional[int] = None
    likes: Optional[int] = None
    scraped_at: Optional[str] = None   # ISO string, kosong = pakai waktu sekarang


# ── Tweet scraper ─────────────────────────────────────────────────────────────

class ScrapeUserTweetsRequest(BaseModel):
    username: str
    max_tweets: int = Field(default=40, ge=1, le=300)
    sentiment_mode: Optional[str] = None   # None | "hybrid" | "rule" | "ml"


class ScrapeRepliesRequest(BaseModel):
    tweet_url: str
    max_replies: int = Field(default=50, ge=1, le=300)
    sort_by: str = Field(default="newest")   # newest | oldest | likes
    sentiment_mode: Optional[str] = None


class ScrapeSearchRequest(BaseModel):
    query: str
    max_tweets: int = Field(default=40, ge=1, le=300)
    search_type: str = Field(default="Latest")   # Latest | Top | Media
    sentiment_mode: Optional[str] = None
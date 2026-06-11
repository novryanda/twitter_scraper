"""
config.py
=========
Konfigurasi terpusat backend, dibaca dari environment variables (.env).
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Server
    API_HOST    = os.getenv("API_HOST", "0.0.0.0")
    API_PORT    = int(os.getenv("API_PORT", "8002"))
    DEBUG       = os.getenv("DEBUG", "True").lower() == "true"

    # CORS — frontend Next.js
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")

    # Paths
    DATA_DIR           = os.path.join(os.getcwd(), "data")
    OUTPUT_PROFILE_DIR = os.path.join(os.getcwd(), "output_profiles")
    SESSION_DIR        = os.path.join(os.getcwd(), "session")
    TWITTER_PROFILE    = os.path.join(os.getcwd(), "twitter_profile")
    TRACKING_FILE      = os.path.join(os.getcwd(), "output_profiles", "growth_tracking.json")

    # Scraper
    HEADLESS        = os.getenv("TWITTER_HEADLESS", "False").lower() == "true"
    PROXY           = os.getenv("TWITTER_PROXY", "")
    DELAY_BETWEEN   = int(os.getenv("TWITTER_DELAY_BETWEEN_PROFILES", "12"))
    MIN_GAP_SECONDS = int(os.getenv("TWITTER_MIN_GAP_SECONDS", "10"))

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    )

    FALLBACK_BEARER = (
        "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
        "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
    )

    def __init__(self):
        for d in (self.DATA_DIR, self.OUTPUT_PROFILE_DIR,
                  self.SESSION_DIR, self.TWITTER_PROFILE):
            os.makedirs(d, exist_ok=True)


settings = Settings()

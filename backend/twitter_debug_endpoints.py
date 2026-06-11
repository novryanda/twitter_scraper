"""
twitter_debug_endpoints.py
==========================
Script untuk capture GraphQL endpoint Twitter/X.
Taruh di: backend/twitter_debug_endpoints.py (sejajar main.py)

Cara pakai:
    python twitter_debug_endpoints.py

Jalankan ulang jika scraper dapat error 404 (queryId expired).
"""

import os
import re
import json
import time
import datetime
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
TWITTER_PROFILE = os.path.join(BASE_DIR, "twitter_profile")
ENDPOINTS_FILE  = os.path.join(BASE_DIR, "twitter_endpoints.json")

FALLBACK_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

TARGET_OPERATIONS = [
    "UserByScreenName",
    "UserTweets",
    "UserTweetsAndReplies",
    "TweetDetail",
    "SearchTimeline",
    "HomeTimeline",
    "HomeLatestTimeline",
]

TRIGGER_PAGES = [
    "https://x.com/home",
    "https://x.com/elonmusk",
    "https://x.com/search?q=python&src=typed_query&f=live",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_endpoint_info(url: str):
    """
    Ekstrak operasi name, queryId, variables_encoded, features_encoded dari URL.
    Return tuple atau None jika bukan target operasi.
    """
    m = re.search(r"/i/api/graphql/([^/]+)/([^?]+)", url)
    if not m:
        return None

    query_id = m.group(1)
    op_name  = m.group(2).split("?")[0]

    if op_name not in TARGET_OPERATIONS:
        return None

    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    variables_encoded = params.get("variables", [""])[0]
    features_encoded  = params.get("features",  [""])[0]

    return op_name, query_id, variables_encoded, features_encoded


# ── Main ──────────────────────────────────────────────────────────────────────

def run_capture():
    print("=" * 60)
    print("  TWITTER ENDPOINT CAPTURE")
    print("=" * 60)

    # Cek profile dir
    if not os.path.exists(TWITTER_PROFILE) or not os.listdir(TWITTER_PROFILE):
        print(f"\n[ERROR] Profile tidak ditemukan: {TWITTER_PROFILE}")
        print("  Import cookies dulu via UI di halaman Session/Login,")
        print("  atau login manual browser sekali.")
        return

    captured     = {}
    bearer_token = FALLBACK_BEARER

    with sync_playwright() as p:
        print(f"\n[*] Membuka browser...")
        print(f"    Profile : {TWITTER_PROFILE}")

        context = p.chromium.launch_persistent_context(
            TWITTER_PROFILE,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-notifications",
                "--disable-infobars",
            ],
            viewport={"width": 1366, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="Asia/Jakarta",
        )

        # Inject session cookies jika ada
        try:
            from app.core import cookie_injector as ci
            if ci.has_valid_session():
                n = ci.inject_cookies_sync(context)
                print(f"[OK] {n} cookies diinject dari session file")
            else:
                print("[!] Session file tidak ada — pakai profile dir saja")
        except Exception as e:
            print(f"[!] Cookie inject skip: {e}")

        page = context.pages[0] if context.pages else context.new_page()

        # ── Intercept semua request GraphQL ──────────────────────────────────
        def on_request(request):
            nonlocal bearer_token
            url = request.url

            # Capture bearer token
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer ") and "AAAA" in auth:
                bearer_token = auth.replace("Bearer ", "").strip()

            # Capture endpoint
            if "/i/api/graphql/" in url:
                result = extract_endpoint_info(url)
                if result:
                    op_name, query_id, variables_enc, features_enc = result
                    if op_name not in captured:
                        captured[op_name] = {
                            "query_id":          query_id,
                            "variables_encoded": variables_enc,
                            "features_encoded":  features_enc,
                        }
                        print(f"  [CAPTURED] {op_name:<32} queryId={query_id[:16]}...")

        page.on("request", on_request)

        # ── Kunjungi halaman trigger ──────────────────────────────────────────
        for i, url in enumerate(TRIGGER_PAGES):
            remaining = [op for op in TARGET_OPERATIONS if op not in captured]
            if not remaining:
                print("\n[OK] Semua operasi sudah ter-capture!")
                break

            print(f"\n[{i+1}/{len(TRIGGER_PAGES)}] Navigasi ke: {url}")
            print(f"    Menunggu  : {', '.join(remaining)}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                time.sleep(3)
                page.evaluate("window.scrollBy(0, 600)")
                time.sleep(2)
                page.evaluate("window.scrollBy(0, 600)")
                time.sleep(2)
            except Exception as e:
                print(f"    [!] Navigation warning (lanjut): {e}")
                time.sleep(3)

        # Tunggu sebentar kalau masih ada yang belum ter-capture
        remaining = [op for op in TARGET_OPERATIONS if op not in captured]
        if remaining:
            print(f"\n[*] Masih kurang: {remaining}")
            print("    Tunggu 10 detik atau navigasi manual di browser...")
            time.sleep(10)

        context.close()

    # ── Tampilkan hasil ───────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  HASIL: {len(captured)}/{len(TARGET_OPERATIONS)} operasi ter-capture")
    print(f"{'=' * 60}")

    if not captured:
        print("\n[ERROR] Tidak ada endpoint yang ter-capture!")
        print("  Kemungkinan penyebab:")
        print("  1. Belum login — import cookies dulu via UI")
        print("  2. Twitter redirect ke halaman login")
        print("  3. Profile dir kosong atau corrupt")
        return

    for op in TARGET_OPERATIONS:
        if op in captured:
            qid = captured[op]["query_id"]
            print(f"  [OK] {op:<32} {qid}")
        else:
            print(f"  [--] {op:<32} tidak ter-capture")

    # Cek operasi wajib
    required         = ["UserByScreenName", "UserTweets", "TweetDetail", "SearchTimeline"]
    missing_required = [op for op in required if op not in captured]
    if missing_required:
        print(f"\n[WARNING] Operasi wajib belum ada: {missing_required}")
        print("  Scraper mungkin tidak bisa jalan penuh.")
        print("  Coba jalankan ulang script ini.")

    # ── Simpan ke file ────────────────────────────────────────────────────────
    output = {
        "bearer_token": bearer_token,
        "captured_at":  datetime.datetime.now().isoformat(),
        "operations":   captured,
    }

    with open(ENDPOINTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[SAVED] {ENDPOINTS_FILE}")
    print(f"  {len(captured)} operasi tersimpan")
    print("\n  Langkah selanjutnya:")
    print("  1. Restart uvicorn: uvicorn main:app --reload --port 8002")
    print("  2. Coba scrape dari UI (isi username saja, bukan URL)")
    print("=" * 60)


if __name__ == "__main__":
    run_capture()
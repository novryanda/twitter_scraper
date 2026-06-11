# 🐦 Twitter / X Scraper UI — Glassmorphism Edition

Web app untuk scraping profil Twitter/X dan tracking pertumbuhan (followers, following, tweets), dengan **frontend Next.js** bertema **glassmorphism** dan **backend FastAPI**. Login memakai **cookie injector** (paste cookies dari ekstensi Cookie-Editor) — sama persis seperti pendekatan project Instagram sebelumnya.

```
┌─────────────────────┐         HTTP/JSON          ┌──────────────────────┐
│  Frontend (Next.js) │  ───────────────────────►  │  Backend (FastAPI)   │
│  localhost:3000     │  ◄───────────────────────  │  localhost:8002      │
│  Glassmorphism UI   │                            │  Playwright + cookies│
└─────────────────────┘                            └──────────────────────┘
```

---

## 📁 Struktur Project

```
twitter-scraper-ui/
├── backend/                  # FastAPI + Playwright
│   ├── main.py               # Entry point (uvicorn main:app)
│   ├── requirements.txt
│   ├── .env.example          # Salin → .env
│   └── app/
│       ├── core/             # config, logger, cookie_injector, responses
│       ├── models/           # Pydantic schemas
│       ├── routers/          # auth, scrape, profiles, debug
│       └── services/         # profile_scraper, tracking, login_worker
│
└── frontend/                 # Next.js (App Router) + glassmorphism
    ├── package.json
    ├── .env.example          # Salin → .env.local
    └── src/
        ├── app/              # dashboard, scrape, tracking, login, debug
        ├── components/       # Sidebar, AuroraBackground, Toast
        ├── lib/api.ts        # Client API ke backend
        └── styles/globals.css
```

---

## 🚀 Quick Start

Butuh **2 terminal**: satu untuk backend, satu untuk frontend.

### 1️⃣ Backend (FastAPI) — port 8002

```bash
cd backend

# (disarankan) virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# install dependency
pip install -r requirements.txt

# install browser Playwright (sekali saja)
playwright install chromium

# siapkan konfigurasi
cp .env.example .env            # Windows: copy .env.example .env

# jalankan server
uvicorn main:app --reload --port 8002
```

Backend siap di **http://localhost:8002**. Cek docs interaktif di **http://localhost:8002/docs**.

### 2️⃣ Frontend (Next.js) — port 3000

```bash
cd frontend

# install dependency
npm install

# siapkan konfigurasi
cp .env.example .env.local      # Windows: copy .env.example .env.local

# jalankan dev server
npm run dev
```

Buka **http://localhost:3000** di browser.

---

## 🔑 Login via Cookie Injector

Scraper butuh sesi login Twitter/X. Caranya pakai cookies dari browser kamu sendiri (tidak menyimpan password):

1. Login ke **https://x.com** di browser biasa (Chrome/Firefox).
2. Install ekstensi **Cookie-Editor**.
3. Buka x.com → klik ikon Cookie-Editor → **Export** → **Export as JSON** (otomatis ter-copy).
4. Di web app, buka halaman **Login / Session**.
5. Paste JSON ke kolom yang tersedia → klik **Import Cookies**.
6. Status berubah jadi **Session Valid** ✅ — siap scraping.

> Cookie wajib: **`auth_token`** dan **`ct0`**. Kalau salah satu tidak ada, import akan ditolak.
> Cookie bisa expired setelah beberapa hari/minggu. Kalau muncul error sesi, ulangi import.

**Alternatif:** tombol **Login via Browser** membuka jendela Chrome untuk login manual, lalu menyimpan cookies otomatis (butuh `TWITTER_HEADLESS=False`).

---

## 🖥️ Halaman Web App

| Halaman | Fungsi |
|---|---|
| **Dashboard** | Ringkasan: jumlah akun ter-track, status sesi, akses cepat |
| **Scrape** | Scrape profil tunggal atau batch (banyak username sekaligus) |
| **Tracking** | Grafik pertumbuhan (followers/following/tweets), filter 7/30/90/365 hari, export CSV, hapus, snapshot manual |
| **Login / Session** | Import cookies, login via browser, status sesi, logout/hard-reset |
| **Debug** | Log backend real-time (auto-refresh), health check, info sistem |

---

## 🔌 Endpoint Backend (REST)

Base URL: `http://localhost:8002/api/v1`

### Auth
| Method | Path | Keterangan |
|---|---|---|
| POST | `/auth/import-cookies` | Import cookies JSON dari Cookie-Editor |
| GET  | `/auth/status` | Status sesi (valid / tidak) |
| GET  | `/auth/session-info` | Detail cookies sesi |
| POST | `/auth/login` | Buka browser untuk login manual |
| POST | `/auth/logout` | Hapus sesi (opsi `hard_reset`) |

### Scrape
| Method | Path | Keterangan |
|---|---|---|
| POST | `/scrape/profile` | Scrape 1 profil (`{"username": "..."}`) |
| POST | `/scrape/profiles/batch` | Scrape banyak profil sekaligus |

### Profiles / Growth
| Method | Path | Keterangan |
|---|---|---|
| GET  | `/profiles` | List semua akun ter-track |
| GET  | `/profiles/{username}` | Detail 1 akun |
| GET  | `/profiles/{username}/growth?days=30` | Analisis pertumbuhan |
| POST | `/profiles/track` | Tambah snapshot manual (backfill) |
| DELETE | `/profiles/{username}` | Hapus data tracking akun |
| GET  | `/profiles/{username}/export-csv` | Export history ke CSV |

### Debug / Health
| Method | Path | Keterangan |
|---|---|---|
| GET  | `/health` | Health check + status sesi |
| GET  | `/debug/logs?lines=200` | Ambil log backend terbaru |
| DELETE | `/debug/logs` | Bersihkan file log |
| GET  | `/debug/system` | Info sistem (paths, versi, dll) |

Dokumentasi Swagger lengkap & bisa dicoba langsung: **http://localhost:8002/docs**

---

## 🐛 Fitur Debug (Penanganan Error)

Backend dibekali beberapa lapis debug agar mudah cari masalah:

1. **Global exception handler** — setiap error tak tertangani dibalas JSON rapi; saat `DEBUG=True` menyertakan **traceback lengkap**.
2. **Endpoint `/api/v1/debug/logs`** — baca log terbaru tanpa buka file.
3. **Panel Debug di UI** — log real-time, di-warnai per level (INFO/WARNING/ERROR), auto-refresh tiap 3 detik.
4. **Request logging middleware** — tiap request tercatat (method, path, status, durasi).
5. **Logging ke file + konsol** — `logs/backend.log` (rotating, maks 5MB × 5 file), konsol berwarna.

Atur mode debug di `backend/.env`:
```env
DEBUG=True     # True saat development, False saat production
```

---

## 🔧 Troubleshooting

| Masalah | Solusi |
|---|---|
| **"Session tidak valid"** saat scrape | Import ulang cookies di halaman Login. Pastikan `auth_token` + `ct0` ada. |
| **Frontend tidak konek ke backend** | Pastikan backend jalan di port 8002 & `NEXT_PUBLIC_API_URL` di `.env.local` benar. Cek juga CORS di `backend/.env`. |
| **`playwright` error / browser tidak ada** | Jalankan `playwright install chromium`. |
| **Login via browser tidak muncul** | Set `TWITTER_HEADLESS=False` di `backend/.env`. Di server tanpa GUI, pakai metode Cookie-Editor. |
| **GraphQL strategy di-skip** | Normal kalau `twitter_endpoints.json` tidak ada — scraper otomatis fallback ke DOM lalu HTML meta. |
| **Port 8002 sudah dipakai** | Ganti `--port` saat menjalankan uvicorn, dan sesuaikan `NEXT_PUBLIC_API_URL`. |
| **CORS error di console browser** | Tambahkan origin frontend ke `CORS_ORIGINS` di `backend/.env`. |

---

## 📝 Catatan Teknis

- **Strategi scrape profil:** GraphQL `UserByScreenName` (utama) → DOM parsing → HTML meta tags (fallback). GraphQL butuh `twitter_endpoints.json` di folder backend; tanpa itu tetap jalan via DOM/HTML.
- **Data tracking** disimpan di `backend/output_profiles/growth_tracking.json` (dibuat otomatis).
- **Cookies sesi** disimpan di `backend/session/tw_session.json` — **jangan di-commit / dibagikan** (sudah masuk `.gitignore`).
- Gunakan dengan **bijak** dan patuhi Terms of Service serta hukum yang berlaku.

---

## 🧰 Stack

**Frontend:** Next.js 15 (App Router), React 19, Recharts, lucide-react, CSS glassmorphism custom.
**Backend:** FastAPI, Uvicorn, Playwright (sync + async), Pydantic v2, python-dotenv.

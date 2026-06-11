# Backend — FastAPI

```bash
python -m venv venv && source venv/bin/activate    # opsional
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
uvicorn main:app --reload --port 8002
```

- Docs Swagger: http://localhost:8002/docs
- Health: http://localhost:8002/api/v1/health
- Log file: `logs/backend.log`

Lihat **README.md** di root untuk dokumentasi lengkap (endpoint, debug, troubleshooting).

## Struktur
- `main.py` — app FastAPI, CORS, middleware logging, global exception handler
- `app/core/` — `config.py`, `logger.py`, `cookie_injector.py`, `responses.py`
- `app/routers/` — `auth.py`, `scrape.py`, `profiles.py`, `debug.py`
- `app/services/` — `profile_scraper.py`, `tracking.py`, `login_worker.py`
- `app/models/schemas.py` — Pydantic request models

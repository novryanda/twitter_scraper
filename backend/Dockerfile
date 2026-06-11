FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DBUS_SESSION_BUS_ADDRESS=/dev/null

WORKDIR /app

# System deps minimal untuk pip + Playwright install-deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium + semua system deps-nya sekaligus
RUN playwright install --with-deps chromium

COPY . .

# Buat direktori runtime agar volume mount tidak error permission
RUN mkdir -p data session output_profiles logs twitter_profile

EXPOSE ${API_PORT:-8002}

CMD ["sh", "-c", "uvicorn main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8002}"]

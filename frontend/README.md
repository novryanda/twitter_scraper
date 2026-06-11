# Frontend — Next.js (Glassmorphism)

```bash
npm install
cp .env.example .env.local
npm run dev
```

Buka http://localhost:3000

> Pastikan backend sudah jalan di port 8002 (lihat `../backend`). Atur target backend lewat `NEXT_PUBLIC_API_URL` di `.env.local`.

## Halaman
- `/dashboard` — ringkasan & akses cepat
- `/scrape` — scrape profil tunggal / batch
- `/tracking` — grafik pertumbuhan, export CSV, snapshot manual
- `/login` — import cookies / login browser / status sesi
- `/debug` — log backend real-time, health, info sistem

## Build production
```bash
npm run build && npm start
```

Lihat **README.md** di root untuk dokumentasi lengkap.

# Laprak

Aplikasi web untuk menyusun laporan apa pun yang berpola **template + dokumentasi bergambar + narasi**. Pengguna masuk dengan Google, mengunggah template LaTeX (ZIP), mengunggah gambar dokumentasi, lalu AI menempatkan gambar dan menulis draf deskripsi. PDF dikompilasi di server.

AI dipanggil **dari browser pengguna** ke 9Router di localhost atau provider lain yang kompatibel OpenAI (base URL + API key). Server hanya menyusun prompt dan memvalidasi jawaban; server tidak pernah memanggil provider. API key disimpan terenkripsi per akun (AES-256-GCM, envelope encryption).

Keputusan arsitektur lengkap ada di [docs/PRD_Laprak_Web_v2.md](docs/PRD_Laprak_Web_v2.md).

## Struktur

```
backend/   FastAPI + SQLModel (SQLite dev, PostgreSQL prod), pipeline LaTeX, prompt builder, enkripsi
frontend/  React 19 + TypeScript + Vite, React Router, TanStack Query, dnd-kit, i18n (id/en)
template/  Template LaTeX ITERA (contoh; terdeteksi otomatis)
docs/      PRD v1 (desktop, arsip) dan PRD v2 (web)
```

## Menjalankan (pengembangan)

Backend (Python 3.11):

```powershell
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
copy .env.example .env        # LAPRAK_DEV_LOGIN=1 mengaktifkan login tanpa Google
.venv/Scripts/python -m uvicorn laprak.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm ci
npm run dev                   # http://localhost:5173, /api diproksikan ke :8000
```

Produksi lokal satu proses: `npm run build` lalu jalankan uvicorn; FastAPI menyajikan `frontend/dist` dan API di `/api`.

Compiler LaTeX dideteksi otomatis (`xelatex` di PATH, MiKTeX, TeX Live). Paksa lokasi dengan `LAPRAK_TEX_COMPILER`.

## Login Google

Buat OAuth Client (Web) di Google Cloud Console, tambahkan redirect URI `<LAPRAK_PUBLIC_URL>/api/auth/callback`, lalu isi `LAPRAK_GOOGLE_CLIENT_ID` dan `LAPRAK_GOOGLE_CLIENT_SECRET`. Pada produksi set `LAPRAK_COOKIE_SECURE=1`, `LAPRAK_SECRET_KEY`, dan `LAPRAK_MASTER_KEY` (32 byte base64) secara eksplisit.

## Alur AI

1. Browser meminta `POST /api/projects/{id}/ai/prepare` → paket prompt (system, pesan, URL gambar bertanda tangan, JSON schema).
2. Browser memanggil `{base_url}/chat/completions` provider pengguna (`frontend/src/ai/runner.ts`). Gambar diunduh dari URL bertanda tangan dan dikirim sebagai data URL.
3. Browser mengirim jawaban mentah ke `POST /api/projects/{id}/ai/complete`; server memvalidasi dengan Pydantic, menyimpan `Draft`, dan hanya menerapkan otomatis bila teks pengguna masih kosong.

Operasi: `analyze_evidence`, `describe_step`, `match_evidence`, `draft_section`, `outline_document`, `scan_template`, `probe`. Prompt dua bahasa ada di `backend/laprak/ai/prompts.py`.

Catatan 9Router: halaman web memanggil `http://localhost:…` langsung dari browser. 9Router harus mengizinkan CORS untuk origin aplikasi, dan Chrome dapat meminta izin akses jaringan lokal satu kali.

## Template

ZIP LaTeX diunggah per proyek. Template ITERA dikenali otomatis; template lain dipetakan lewat UI **Template → Pemetaan slot**: berkas utama, engine, perintah identitas (`\namapeserta` → `name`), `\input` identitas yang diganti atau penanda `% LAPRAK_IDENTITY`, dan berkas tiap slot (`documentation` wajib, lainnya opsional: `discussion`, `conclusion`, `theory`, `tools`, `tasks`, `references`, `summary`). Template asli tidak diubah; build memakai salinan kerja.

Konversi DOCX → template LaTeX dasar, worker antrean (arq), dan Docker Compose menyusul sesuai tahapan di PRD v2.

## Uji

```powershell
cd backend;  .venv/Scripts/python -m pytest          # API, enkripsi, prompt, render LaTeX, build PDF nyata bila compiler ada
cd frontend; npm run typecheck; npm run build
cd frontend; node scripts/smoke.mjs http://127.0.0.1:8000   # alur browser penuh dengan Chrome headless (butuh LAPRAK_DEV_LOGIN=1)
```

Screenshot hasil smoke berada di `.local/web-qa/`.

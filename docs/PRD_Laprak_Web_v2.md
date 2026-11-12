# PRD — Laprak Web v2 (laporan umum, AI milik pengguna)

Versi: 2.0 draf
Tanggal: 12 November 2026
Status: keputusan arsitektur untuk rombak total dari desktop Qt ke aplikasi web
Menggantikan: `PRD_Laprak_Jarkom_AI.md` (v1, desktop, khusus Jaringan Komputer)

## 1. Ringkasan

Laprak menjadi aplikasi web untuk menyusun laporan apa pun yang berpola
"template + urutan dokumentasi bergambar + narasi". Pengguna masuk dengan akun
Google, mengunggah template (LaTeX atau DOCX), mengunggah gambar dokumentasi,
dan AI menyusun urutan serta menulis deskripsi. PDF dan sumber LaTeX dihasilkan
server. AI dipanggil dari browser pengguna ke 9Router miliknya sendiri atau ke
provider lain dengan base URL dan API key; server tidak pernah memanggil AI.

## 2. Keputusan yang sudah diambil

| # | Keputusan | Konsekuensi |
| --- | --- | --- |
| 1 | AI dipanggil dari browser ke 9Router/provider pengguna, bukan dari server | Server menyusun paket prompt, browser mengeksekusi, hasil dikirim balik untuk divalidasi |
| 2 | Template LaTeX dipakai apa adanya; DOCX dikonversi menjadi template LaTeX dasar yang meniru tata letak DOCX | Perlu konverter DOCX→LaTeX dan pembanding visual |
| 3 | Login Google, proyek tersimpan di server | Perlu auth OAuth, database multi pengguna, penyimpanan file per akun |
| 4 | Dokumen sumber (modul/SOP/brief) opsional | Langkah bisa dibuat manual, dari dokumen, atau dari gambar |
| 5 | Codex OAuth dan OpenCode Zen dihapus | Satu adapter kompatibel OpenAI, opsional adapter Anthropic native |
| 6 | API key disimpan terenkripsi per akun di server | Envelope encryption; key dikirim ke browser hanya saat dibutuhkan lewat TLS |
| 7 | Bahasa Indonesia default, Inggris sebagai opsi | i18n UI dan prompt dua bahasa, bahasa laporan per proyek |
| 8 | Stack melanjutkan yang ada: React + TypeScript + Vite, Python | FastAPI menggantikan Qt WebChannel; pipeline Python dipertahankan |

## 3. Catatan risiko utama: browser → localhost

Halaman HTTPS yang memanggil `http://localhost` diizinkan Chrome karena
localhost dianggap konteks aman, tetapi dua syarat harus dipenuhi:

- 9Router harus mengirim header CORS untuk origin aplikasi. Jika tidak,
  pengguna diarahkan menyalakan opsi CORS di 9Router atau memakai proxy lokal
  kecil yang kita sediakan.
- Kebijakan Local Network Access Chrome dapat meminta izin pengguna sekali.
  UI harus menjelaskan prompt ini.

Fallback resmi: pengguna mengisi base URL provider publik (OpenRouter, Groq,
Anthropic, OpenAI). Tetap dipanggil dari browser, bukan server, agar prinsip
nomor 1 konsisten dan server tidak pernah memegang lalu lintas AI.

## 4. Arsitektur

```
Browser (React)                       Server
├─ UI proyek, template, dokumentasi   ├─ FastAPI: auth, proyek, file, prompt, validasi
├─ AI Runner (antrean klien,          ├─ PostgreSQL (SQLite untuk dev)
│  retry, cancel, satu job aktif)     ├─ Object storage (folder lokal / S3)
│   └─ fetch → 9Router / provider     ├─ Worker (arq + Redis): kompilasi LaTeX, konversi DOCX,
└─ Pratinjau PDF                      │  thumbnail, render pembanding
                                      └─ Kontainer TeX Live + LibreOffice headless
```

Alur AI: browser minta `POST /projects/{id}/ai/prepare` dengan jenis operasi →
server mengembalikan paket (system prompt, pesan, URL gambar bertanda tangan,
JSON schema, bahasa) → browser memanggil provider → browser kirim
`POST /ai/complete` dengan jawaban mentah → server memvalidasi Pydantic,
menyimpan sebagai draf, dan mengembalikan hasil terstruktur. Logika prompt dan
validasi tetap di Python dan dapat diuji tanpa browser.

## 5. Model domain (generik)

- **Project**: pemilik, judul, bahasa laporan, template aktif, identitas (peta
  nama→nilai bebas, mengikuti slot template), status.
- **SourceDocument** (opsional): PDF/DOCX/MD; diekstrak menjadi teks berhalaman
  dan daftar **Step** usulan.
- **Step**: urutan, judul, instruksi sumber (opsional), catatan pengguna,
  kumpulan **Evidence** (gambar), deskripsi (manual atau draf AI), status
  tinjau.
- **Evidence**: file gambar, hash, EXIF time, urutan dalam step, fakta hasil
  vision (opsional, dapat dikoreksi).
- **Template**: jenis (latex | docx_converted), berkas asli, berkas kerja,
  **SlotMap** (identitas, daftar langkah, bagian naratif bebas seperti
  pembahasan/kesimpulan), engine, status validasi.
- **Section**: bagian naratif non-langkah yang ditemukan di template
  (pembahasan, kesimpulan, teori, dll.), isi manual atau draf AI.
- **Draft**: riwayat keluaran AI per target, tidak pernah menimpa teks pengguna.
- **Build**: snapshot sumber, log, PDF, status; PDF final terkunci jika ada
  kekurangan.
- **AIProfile**: nama, base URL, model teks, model vision, API key terenkripsi,
  hasil uji kemampuan.

## 6. Template

### 6.1 LaTeX dari pengguna
1. Unggah ZIP. Server memvalidasi path, menolak shell escape, menemukan
   `main.tex` atau meminta pengguna memilih.
2. Pemindai slot heuristik + AI teks: menebak perintah identitas (`\newcommand`,
   `\def`, berkas `data/*.tex`), lokasi daftar dokumentasi (loop/`\input`
   berulang, bagian berjudul dokumentasi/langkah/hasil), dan bagian naratif.
3. Pengguna mengonfirmasi SlotMap lewat UI (pilih baris kode untuk tiap slot).
   Tidak ada manifest JSON manual.
4. Kompilasi uji di worker dengan data dummy; hasil wajib hijau sebelum dipakai.

### 6.2 DOCX dari pengguna → template LaTeX dasar
1. Baca `python-docx`: ukuran halaman, margin, orientasi, font tubuh dan
   heading, ukuran, spasi, header/footer, tabel identitas, daftar/penomoran,
   gambar logo.
2. Hasilkan `main.tex` XeLaTeX dengan `geometry`, `fontspec` (font pengganti
   jika font tidak tersedia, dengan peta pengganti yang ditampilkan ke
   pengguna), `fancyhdr`, `titlesec`, `caption`, dan slot yang sama seperti
   6.1.
3. Render DOCX asli ke PDF lewat LibreOffice headless dan kompilasi hasil LaTeX;
   tampilkan berdampingan halaman per halaman agar pengguna menilai kemiripan
   dan dapat menyesuaikan margin/font lewat form.
4. Target presisi: ukuran halaman, margin, font, ukuran heading, header/footer
   identik; detail minor diterima sebagai beda wajar.

## 7. Dokumentasi dan penempatan gambar

1. Drag and drop banyak gambar; unggah paralel, thumbnail dibuat worker.
2. Urutan awal: nama file numerik → EXIF/waktu ubah → urutan unggah.
3. Jika ada daftar Step (dari dokumen sumber atau manual), AI vision
   mencocokkan tiap gambar ke step dengan skor keyakinan; keyakinan rendah
   ditandai untuk ditinjau. Tanpa Step, AI mengelompokkan gambar menjadi step
   usulan berdasarkan kemiripan konten dan waktu.
4. Pengguna memindahkan gambar antar step dengan dnd-kit; perubahan ini
   membatalkan persetujuan deskripsi terkait.
5. Deskripsi per step dibuat dengan konteks: gambar step, catatan, instruksi
   sumber, dan ringkasan step sebelumnya agar narasi runtut. Bahasa mengikuti
   proyek.
6. Bagian naratif (pembahasan, kesimpulan) dibuat dari step yang sudah
   ditinjau saja.

## 8. Keamanan

- OAuth Google Authorization Code + PKCE, sesi cookie HttpOnly SameSite=Lax,
  CSRF token untuk mutasi.
- Enkripsi API key: master key server (env/KMS) membungkus data key per
  pengguna; nilai dienkripsi AES-256-GCM. Key tidak pernah masuk log, ekspor
  ZIP, atau respons selain endpoint khusus `GET /ai-profiles/{id}/secret`
  dengan rate limit.
- File per pengguna berada di prefix terpisah; akses lewat URL bertanda tangan
  berumur pendek.
- Kompilasi LaTeX di kontainer tanpa jaringan, `-no-shell-escape`, timeout,
  batas ukuran, direktori sementara.
- Server tidak menyimpan prompt/jawaban AI mentah lebih dari yang perlu untuk
  riwayat draf.

## 9. Tech stack final

| Lapisan | Pilihan |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, React Router, TanStack Query, dnd-kit, react-pdf, react-i18next, token desain `tokens.css` yang ada |
| Backend | Python 3.11, FastAPI, SQLModel + Alembic, Pydantic v2, httpx, Authlib (Google OAuth), cryptography |
| Database | PostgreSQL (produksi), SQLite (dev/test) |
| Job | arq + Redis; worker image berisi TeX Live dan LibreOffice |
| File | abstraksi storage: folder lokal → S3 kompatibel |
| Dokumen | pypdf, python-docx, Pillow |
| Deploy | Docker Compose: web (nginx static), api, worker, redis, postgres |
| Uji | pytest untuk pipeline/prompt, Playwright untuk alur browser dengan mock provider |

Kode yang dibawa: `ai.py` (schema, validasi, adapter OpenAI-compatible, cache
key), `report.py` (generate, build sandbox, diagnosis), `images.py`,
`module_review.py` (jadi ekstraksi dokumen sumber generik), `storage.py`
(skema proyek sebagai dasar model SQLModel), dan `frontend/src/tokens.css`.
Kode yang dibuang: `app.py`, `desktop.py`, `dialogs.py`, `widgets.py`,
`workflow.py`, `style.py`, `codex.py`, `zen.py`, `react_bridge.py`,
`installer/`, `scripts/package.ps1`.

## 10. Tahapan

1. **Fondasi server**: FastAPI, auth Google, model data, storage, migrasi;
   port `ai.py` dan `report.py` tanpa Qt. Uji pytest.
2. **Frontend ulang**: pecah `App.tsx` menjadi halaman (Beranda proyek,
   Template, Dokumentasi, Periksa, PDF, Pengaturan AI), klien HTTP, i18n.
3. **AI Runner di browser**: antrean klien, uji koneksi dan vision, profil AI
   terenkripsi, alur prepare/complete.
4. **Template**: unggah LaTeX + pemindai slot + konfirmasi UI; konverter DOCX
   → LaTeX dengan pembanding visual.
5. **Dokumentasi**: unggah massal, pengurutan, pencocokan AI, deskripsi,
   riwayat draf, bagian naratif.
6. **Render dan rilis**: worker TeX Live, pratinjau, ekspor ZIP, Docker
   Compose, Playwright, dokumentasi pengguna.

# Aturan untuk semua asisten AI (Claude, Codex, Copilot, Cursor, Gemini, dan lainnya)

## Atribusi commit

- **Jangan pernah** menambahkan diri sebagai co-author. Dilarang menulis trailer `Co-Authored-By:`, `Co-authored-by:`, `Signed-off-by:` atas nama AI, atau baris seperti `Generated with ...`, `Made with ...`, `🤖 ...` di pesan commit, badan PR, deskripsi issue, atau changelog.
- Author dan committer selalu identitas Git milik pengguna. Jangan mengubah `user.name` / `user.email`.
- Hook `.githooks/commit-msg` membuang baris atribusi AI secara otomatis. Aktifkan sekali per clone:

  ```bash
  git config core.hooksPath .githooks
  ```

## Gaya commit

- Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`; subjek bahasa Inggris, imperatif, maksimal 72 karakter.
- Satu commit untuk satu bagian pekerjaan yang utuh (backend, frontend, docs, dan seterusnya), bukan satu commit raksasa.
- Commit dan push hanya ketika pengguna memintanya.

## Proyek

- Backend: `backend/` (FastAPI, Python 3.11, venv di `backend/.venv`). Uji: `.venv/Scripts/python -m pytest`.
- Frontend: `frontend/` (React + TypeScript + Vite). Uji: `npm run typecheck && npm run build`; alur browser: `npm run smoke` dengan backend berjalan dan `LAPRAK_DEV_LOGIN=1`.
- Keputusan arsitektur: `docs/PRD_Laprak_Web_v2.md`. AI dipanggil dari browser pengguna, tidak pernah dari server. API key tidak boleh masuk log, snapshot, atau ekspor.

# Laprak

Aplikasi desktop Windows untuk menyusun laporan praktikum Jaringan Komputer. Implementasi mengikuti PRD di `docs/PRD_Laprak_Jarkom_AI.md` dan workspace tiga panel pada `design/Laprak Packet Tracer Report Workspace.png`.

## Menjalankan

Di workspace ini dependensi sudah terpasang. Klik **Jalankan Laprak.cmd**, atau jalankan:

```powershell
.venv/Scripts/python -m laprak
```

Untuk instalasi dari checkout baru:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock.txt
.venv/Scripts/python -m laprak
```

Data pengaturan dan daftar sesi berada di `.local/`, yang dikecualikan dari Git. Sesi disimpan di folder yang dipilih pengguna. `--data-dir <folder>` memindahkan pengaturan, dan `--session <folder>` membuka sesi tertentu. Python 3.11 x64 dan Windows menjadi lingkungan pengembangan awal.

## Alur penggunaan

### Login GPT melalui Codex

Buka **Pengaturan → Provider AI → Connect GPT**. Browser membuka halaman login resmi Codex. Setelah login berhasil, kembali ke Laprak: status berubah otomatis dan model bawaan akun terpilih. Klik **Simpan pengaturan**, lalu **Uji koneksi AI** untuk memeriksa akses model. Tidak perlu memasukkan API key, alamat server, atau password di Laprak. Kemampuan gambar tetap harus diuji sebelum dipakai.

Codex CLI harus terpasang dan tersedia di PATH (di komputer pengembangan ini sudah terpasang). Untuk komputer baru, lihat [panduan resmi Codex CLI](https://developers.openai.com/codex/cli/). Penggunaan model mengikuti akses dan batas kuota akun; login berhasil belum menjamin kuota model tersedia.

Laprak menggunakan protokol resmi `codex app-server`, login browser `account/login/start`, dan notifikasi `account/login/completed`. Akun Laprak terpisah dari akun/config Codex untuk coding: `CODEX_HOME` khusus berada di `.local/codex`, dengan kredensial dikelola Codex melalui Credential Manager Windows (`keyring`). Laprak tidak membaca atau menyalin token OAuth. Analisis memakai thread sementara, direktori sementara, sandbox read-only, shell/web dinonaktifkan, dan respons JSON tervalidasi. **Batalkan login** menutup proses dan listener milik Laprak; menutup pengaturan juga membatalkan proses yang sedang berjalan.

Verifikasi protokol tanpa membuka browser atau memakai kuota: `.venv/Scripts/python.exe -m tests.codex_protocol_smoke`.

1. Pilih **Sesi → Sesi baru**, isi identitas, lalu pilih folder kosong.
2. **Pengaturan → Compiler dan template**: pilih template dan compiler. Jalankan pemeriksaan versi, dokumen kecil, dan template asli. Build tetap terkunci sampai pemeriksaan berhasil pada peluncuran ini.
3. **Upload modul** PDF. Teks dan render disimpan per halaman. Pada **Periksa struktur**, koreksi teks/struktur JSON atau analisis dengan AI, lalu setujui struktur. Nomor halaman selalu nomor halaman file PDF; nomor tercetak disimpan terpisah bila diisi pada data modul.
4. Buat langkah, klik instruksi di **Panduan modul** untuk memasang/melepas pemetaan ke langkah aktif. Klik kanan langkah untuk mengubah judul, urutan, atau alasan tidak berlaku.
5. **Impor gambar** atau pilih folder screenshot eksternal. Gambar baru harus stabil sebelum diimpor; PNG/JPEG divalidasi dan disalin. Pilih penempatan ke langkah aktif atau langkah baru. Tahap yang ditangkap saat event diterima dipertahankan walaupun pilihan langkah berubah.
6. Klik kanan thumbnail untuk memindahkan, mengurutkan, menghapus dari laporan, membuat crop/resize turunan, atau memulihkan gambar asli.
7. Koreksi **Fakta konfigurasi**, tandai fakta diperiksa, isi penjelasan dan dua pemeriksaan, lalu **Setujui langkah**. Hasil gagal dan sebagian sukses merupakan hasil yang sah untuk didokumentasikan.
8. Lengkapi **Bagian laporan & checklist**. Rangkuman, teori, alat, tugas, referensi, pembahasan, dan kesimpulan bisa ditulis manual dan tersimpan otomatis. AI pembahasan/kesimpulan hanya menerima langkah yang diperiksa; hasilnya harus diterapkan secara eksplisit. Tandai persetujuan bagian laporan setelah memeriksa isi dan sumbernya.
9. **Build PDF** menghasilkan draf dari snapshot. Preview terakhir tetap tersedia jika build gagal. **Ekspor → proyek ZIP** tersedia untuk draf; **PDF final** memerlukan pemeriksaan lengkap dan build revisi terbaru.

Gunakan tiga backtick untuk blok CLI; isi blok dimasukkan lewat `lstinputlisting`, sedangkan teks biasa di-escape terpusat. Perintah LaTeX yang ditulis pada editor diperlakukan sebagai teks.

## Skema AI per pengguna

Pengguna membawa akses AI sendiri; aplikasi tidak menyediakan akun atau model bersama. Pilihan awal:

| Adapter | Endpoint dasar | Kebutuhan |
| --- | --- | --- |
| API kompatibel OpenAI | URL HTTPS berakhir `/v1`, sesuai provider | Model dan API key dari provider; dukungan kompatibilitas harus diuji |
| Ollama | `http://localhost:11434` | Ollama berjalan dengan model yang sudah tersedia secara lokal |
| OpenCode Zen (API) | `https://opencode.ai/zen/v1` | API key Zen dan ID model dari daftar; adapter langsung mendukung Chat Completions |

### Menggunakan API OpenCode Zen langsung

Pilih **OpenCode Zen (API)**, isi API key dari akun Zen, klik **Pilih model**, lalu **Uji koneksi AI**. Jalur ini berjalan langsung via HTTPS tanpa server lokal. Daftar hanya menawarkan model Chat Completions berbayar dengan protokol terverifikasi; pemanggilan dapat memakai saldo akun. Model gratis Zen diblokir sebelum permintaan API langsung karena layanan membatasi free tier ke OpenCode. `free` bukan ID model. Format bawaan **Prompt JSON** menghindari asumsi dukungan JSON schema pada semua model.

Pengaturan lama yang memilih OpenCode server tetapi memakai alamat Zen diperbaiki saat dialog dibuka; pengaturan server OpenCode lama lainnya direset ke API kompatibel OpenAI agar diisi ulang. Password server tidak disalin menjadi API key Zen. Pesan koneksi selalu terlihat di bawah halaman. HTTP 403 tidak langsung dianggap API key salah: adapter membedakan FreeTierError, key tidak valid, kuota, proteksi jaringan, dan penolakan akses yang belum diketahui tanpa menampilkan isi respons mentah.

Uji nyata Big Pickle melalui API langsung mendapat FreeTierError. Mengganti API key atau alamat ke localhost belum menyelesaikan pembatasan tersebut. Referensi: [OpenCode Zen](https://opencode.ai/docs/zen/) dan [konfirmasi batasan free tier oleh maintainer](https://github.com/anomalyco/opencode/issues/49621).

Pengaturan koneksi berada di tab **Provider AI**. Format JSON, waktu tunggu, ukuran gambar, antrean, dan batas PDF berada di tab **Lanjutan**. Scroll di atas kolom angka/pilihan menggulir halaman tanpa mengubah nilainya; perubahan dilakukan lewat ketikan, keyboard, atau tombol panah. Tombol uji koneksi dan simpan tetap tersedia di bagian bawah dialog.

Adapter ada di `laprak/ai.py`. Aplikasi dan antrean menggunakan operasi internal `analyze_module`, `analyze_screenshot`, `generate_explanation`, `generate_discussion`, dan `generate_conclusion`, bukan format API provider. Adapter mengubah prompt/schema/gambar ke format endpoint. Menambah provider dengan API berbeda dilakukan di batas adapter tersebut.

**Uji koneksi AI** memakai teks contoh dan, jika opsi vision dipilih, gambar kode acak. Kemampuan vision harus berhasil diuji sebelum opsi tersebut dapat disimpan. Hasil uji terikat provider, endpoint, model, dan format keluaran. Uji ini memverifikasi format respons dan kemampuan dasar; kualitas analisis praktikum tetap harus diperiksa pengguna.

Mode keluaran **JSON**, **JSON schema**, dan **Prompt JSON** mengakomodasi perbedaan endpoint. Semua hasil tetap divalidasi Pydantic. Gambar/PDF asli tidak dikirim utuh otomatis: modul dibagi per lima halaman; bukti mengirim gambar langkah terpilih dan konteksnya; pembahasan/kesimpulan menerima langkah diperiksa. Tidak ada asumsi PDF native.

API key disimpan melalui backend Windows Credential Manager. Jika backend aman tidak tersedia, key hanya bertahan dalam memori. Endpoint tidak boleh memuat username, password, query, atau fragment. Kredensial tidak masuk data sesi, log error, atau ZIP. Tidak ada telemetry maupun backend pusat.

Satu job AI berjalan pada satu waktu. Antrean, percobaan, dan hasil cache tersimpan di SQLite. Retry sementara maksimal tiga percobaan dengan backoff dan `Retry-After`; autentikasi gagal menjeda antrean. Job berjalan saat crash menjadi `interrupted`. Job bisa dicoba ulang atau dibatalkan lewat **Antrean**. Pembatalan mengabaikan respons; permintaan HTTP berakhir sesuai timeout.

Edit pengguna selalu dipertahankan: hasil AI yang bertabrakan dengan revisi baru atau penjelasan yang sudah ada disimpan di **Riwayat revisi**. Pengguna memilih penerapannya. Pergantian bukti/konteks membatalkan persetujuan lama.

Format API dirujuk dari [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) dan [Ollama Chat](https://docs.ollama.com/api/chat). Dukungan provider lain tidak dianggap terjamin hanya karena mengiklankan kompatibilitas.

## Template ITERA yang diberikan

Template di `template/` terdeteksi sebagai **XeLaTeX, B5 176 × 250 mm**. Font yang diperlukan meliputi Garamond, Arial/Arial Black, Bernard MT Condensed, dan Cambria. Logo serta layout asli dipertahankan. Compiler MiKTeX pada mesin pengembangan ditemukan di `D:/Mixtex/miktex/bin/x64/miktex-xetex.exe`; lokasi ini merupakan kandidat deteksi, bukan syarat untuk perangkat lain.

Template asli tidak diubah. Adaptasi dibuat pada salinan sesi dan manifest-nya ditulis di `session/template/manifest.json`. Identitas diganti pada salinan build melalui `generated/identity.tex`; bagian `isi/` mengacu ke file generated. Gambar dibatasi oleh `linewidth` dan `textheight`, rasio tetap dijaga. Antrean float di-flush per gambar agar sesi besar tidak melampaui batas TeX.

Build memakai argumen subprocess terpisah, `-no-shell-escape`, timeout, dan direktori terpisah. `latexmk` digunakan bila tersedia bersama launcher engine standar; pemasangan tanpa launcher standar memakai dua pass engine secara langsung. Paket tidak dipasang otomatis. MiKTeX sendiri dapat memeriksa metadata pembaruan distribusinya; aplikasi tidak mengunduh installer/compiler. MiKTeX atau TeX Live dapat dipilih, termasuk lokasi executable manual.

ZIP berisi database, modul, bukti asli/turunan, template asli sesi, data portable, dan file generated. Jika pernah dibangun, `report/template/main.tex` berisi sumber build lengkap dengan `report/generated` dan `report/screenshots`; kompilasi dari folder `report/template` mereproduksi snapshot build terakhir. Snapshot tersebut bisa lebih lama dari data editor: preview menandai revisi lama. Impor memvalidasi path ZIP dan me-reset lokasi watcher/verifikasi compiler.

## Manifest untuk template lain

Template lain perlu adaptasi eksplisit. Gunakan `main.tex`, tandai posisi definisi identitas dengan `% LAPRAK_IDENTITY`, dan sediakan file slot berikut. Isi file slot diubah hanya pada salinan build.

```json
{
  "schema_version": 1,
  "name": "Template pengguna",
  "main": "main.tex",
  "engine": "xelatex",
  "identity_fields": {"namapeserta": "name", "nim": "nim", "judul": "title"},
  "slots": {
    "documentation": "isi/dokumentasi.tex",
    "theory": "isi/dasar-teori.tex",
    "tools": "isi/alat-dan-bahan.tex",
    "tasks": "isi/tugas.tex",
    "references": "isi/referensi.tex",
    "summary": "isi/rangkuman.tex"
  },
  "required_assets": []
}
```

Untuk template yang sudah memiliki definisi identitas, `identity_inputs` dapat berisi daftar argumen `\\input{...}` yang diganti oleh satu input generated. Template wajib menyediakan `graphicx`, caption, dan struktur dokumen yang sesuai. Konversi template sembarang tidak dilakukan otomatis.

## Validasi

```powershell
.venv/Scripts/python -m unittest discover -s tests -p test_*.py -v
.venv/Scripts/python tests/gui_smoke.py
.venv/Scripts/python tests/build_smoke.py
```

Uji compiler terakhir membutuhkan lingkungan MiKTeX/font milik pengguna. Hasil pengujian pengembangan disimpan di `.local/qa` dan `.local/build-qa`, terpisah dari laporan pengguna. Tiga puluh satu pengujian otomatis serta uji GUI lulus, termasuk konteks tahap screenshot, perlindungan edit dari respons usang, gambar, JSON, pembatalan saat inferensi menunggu, timeout, dan pembersihan sesi. Uji respons model memakai `httpx.MockTransport`; inferensi nyata Zen diuji dan ditolak FreeTierError; keberhasilan inferensi provider lain belum terverifikasi. Uji build sebelumnya memakai **data uji sintetis**, 50 gambar, blok CLI, karakter khusus, dan template yang diberikan. PDF berhasil berisi 53 halaman; beberapa halaman dirender dan diperiksa untuk margin/caption/rasio.

Ekstraksi menggunakan [pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html); render dan preview menggunakan [Qt PDF](https://doc.qt.io/qtforpython-6/PySide6/QtPdfWidgets/QPdfView.html). Pilihan ini menghindari penambahan PyMuPDF pada distribusi awal. Tetap tinjau lisensi semua dependensi/aset/font sebelum mendistribusikan aplikasi.

## Packaging Windows

```powershell
.venv/Scripts/python -m pip install pyinstaller
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package.ps1
```

Jalankan `dist/Laprak/Laprak.exe` dan distribusikan **seluruh folder** `dist/Laprak`. Bundel Windows x64 telah dibuat dan startup offscreen-nya berhasil diuji, termasuk ketersediaan Qt PDF, pada mesin pengembangan. Template pengguna tidak dibundel otomatis. `installer/Laprak.iss` tersedia untuk membangun installer dengan Inno Setup; installer membuka wizard pemeriksaan tanpa memasang TeX secara diam-diam. Installer belum dibangun karena Inno Setup tidak tersedia di mesin ini. Packaging mengikuti [dokumentasi PyInstaller](https://pyinstaller.org/en/stable/usage.html).

## Batas validasi saat ini

- Belum ada modul/screenshot praktikum nyata dari pengguna untuk menguji kualitas ekstraksi dan analisis AI secara menyeluruh.
- Belum ada akses provider nyata; uji koneksi di aplikasi perlu dijalankan dengan model pengguna.
- Belum diuji di mesin Windows 10/11 bersih; kompatibilitas bundel dan installer perlu validasi distribusi.
- Jalur build dua pass telah diuji. Jalur `latexmk` belum diuji pada mesin ini; bibliografi kompleks memerlukan adaptasi template tambahan.
- Status fakta/instruksi tersedia, tetapi UI koreksi struktur modul masih berbentuk JSON; nomor halaman tercetak belum memiliki kontrol UI khusus.

Ini implementasi awal yang dapat dijalankan dan diuji lokal. Batas validasi tersebut harus diselesaikan sebelum mengklaim seluruh kriteria penerimaan PRD telah lolos.

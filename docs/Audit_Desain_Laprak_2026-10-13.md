# Audit desain Laprak — 13 Oktober 2026

Audit berdasarkan PRD, referensi `design/Laprak Packet Tracer Report Workspace.png`, source UI saat ini, render terbaru workspace kosong 1280×720, render pengaturan GPT, serta render QA workspace terisi. Ini audit antarmuka dan alur; belum merupakan pengujian pengguna atau pengukuran aksesibilitas lengkap. Render workspace terisi memakai data sintetis.

## Kesimpulan

Tampilan menyerupai referensi, tetapi referensi hanya menunjukkan kondisi saat pekerjaan sudah berjalan. Implementasi belum memberi pengalaman yang jelas untuk memulai, menyiapkan, memeriksa, dan menyelesaikan laporan. Mengganti warna dan radius tombol saja tidak menyelesaikan masalah utama ini.

## Temuan dan prioritas

| Prioritas | Temuan konkret | Dampak | Perbaikan |
|---|---|---|---|
| P0 | Workspace kosong tetap menampilkan tiga panel, banyak kontrol nonaktif, dan peringatan pemeriksaan. Membuat laporan baru tersembunyi di tombol Sesi. | Pengguna tidak mengetahui tindakan pertama. | Halaman awal dengan Buat laporan baru dan Lanjutkan laporan; setup dipandu setelah membuat laporan. |
| P0 | Periksa struktur modul membuka editor Struktur JSON. | Pemeriksaan tugas membutuhkan pengetahuan format data. | Daftar tugas yang dapat diedit: judul, instruksi, halaman sumber, bukti yang dibutuhkan. JSON hanya untuk mode lanjutan. |
| P0 | Setup, screenshot, fakta, penjelasan, bagian laporan, build dan ekspor tersebar di area berbeda tanpa navigasi proses. | Pengguna harus mengingat sendiri urutan dan hubungan fitur. | Navigasi Persiapan → Dokumentasi → Periksa laporan → PDF. |
| P1 | AI di status bar ditentukan oleh keberadaan nama model. | Pilihan model terlihat seperti status koneksi meskipun belum diuji. | Pisahkan Belum login, Login berhasil, Model belum diuji, Siap digunakan, dan Gangguan koneksi. |
| P1 | Connect GPT masih berdampingan dengan Provider, Model, Pilih model, checkbox dukungan gambar, Uji koneksi, dan Simpan. | Login satu klik masih terasa seperti konfigurasi teknis. | Halaman Hubungkan AI yang memprioritaskan login; model dan provider lain ditempatkan di Pengaturan lanjutan. Deteksi kemampuan dan tampilkan hasil pemeriksaan. |
| P1 | Setujui langkah tampil hijau saat workspace kosong, sementara sebagian kontrol lain jelas abu-abu. Peringatan IP muncul sebelum ada bukti. | Prioritas dan kondisi tindakan sulit dibaca. | Styling nonaktif yang konsisten; peringatan hanya ketika relevan. |
| P1 | Analisis, Buat ulang, dan Setujui langkah berada di dua panel; pemeriksaan fakta berada pada tab lain. | Dampak tindakan serta prasyarat persetujuan kurang jelas. | Satu urutan lokal: Tambahkan screenshot → Buat draf dengan AI → Periksa → Tandai selesai. Tampilkan kekurangan dekat tombol. |
| P1 | Build PDF dan Ekspor terpisah; Ekspor memperoleh aksen utama. Compiler belum diperiksa muncul sebagai status tanpa tindakan langsung. | Tujuan akhir dan penyebab PDF belum tersedia kurang jelas. | Area PDF dengan Buat PDF, Pratinjau, Simpan PDF dan diagnosis yang dapat ditindaklanjuti. Ekspor proyek merupakan aksi sekunder. |
| P2 | Dokumentasi dan Panduan modul menjadi dua daftar sejajar; keterkaitan memerlukan klik pemetaan dan informasi tooltip. | Tugas modul dan langkah yang dibuat mudah tertukar. | Tampilkan tugas sumber dan halaman pada langkah yang sedang dibuka; panduan menjadi panel tambahan. |
| P2 | Tiga panel memiliki minimum lebar 250/390/330 px. Judul langkah dibatasi elipsis 118 px. Di render 1280×720 area gambar kosong memiliki scrollbar dan ruang kosong besar. | Ruang kerja terasa sempit meskipun sebagian permukaan kosong; nama langkah sulit dipindai. | Dua panel utama, pemeriksaan opsional, judul dua baris, dan aturan ukuran gambar/thumbnail yang menyesuaikan ruang. Validasi juga pada skala Windows 125%/150%. |
| P2 | Istilah Sesi, Build PDF, Upload, Compiler, Struktur JSON, Fakta konfigurasi dan Connect GPT bercampur. | Pengguna harus menerjemahkan istilah sebelum memahami tujuan. | Gunakan Laporan, Buat PDF, Unggah modul, Kesiapan PDF, Periksa tugas, Data yang terbaca dan Hubungkan GPT. |

## Opsi redesign

### A. Rapikan workspace yang ada

Pertahankan tiga panel dan sebagian besar navigasi. Tambahkan halaman awal, satu tindakan utama per area, label yang lebih jelas, formulir pemeriksaan modul, dan status yang akurat. Perubahan relatif kecil, paling dekat dengan desain awal. Kekurangan: pengguna tetap berhadapan dengan banyak fitur bersamaan.

### B. Alur sepenuhnya bertahap

Pisahkan Identitas → Modul → Screenshot → Penjelasan → Periksa → PDF menjadi halaman dengan tombol Lanjut dan Kembali. Paling mudah dipelajari untuk penggunaan pertama. Kekurangan: membandingkan bukti dengan narasi dan bolak-balik antar langkah menjadi lebih lambat. Tahapan tetap harus bisa dikunjungi ulang, dan mode manual tidak dikunci oleh ketersediaan AI.

### C. Persiapan terpandu + editor yang fokus — rekomendasi

Halaman awal menampilkan Buat laporan baru dan Lanjutkan laporan. Persiapan memandu identitas, modul, template, dan AI opsional. Workspace dokumentasi memiliki daftar langkah di kiri dan editor luas di kanan. Editor menampilkan screenshot dan penjelasan bersama; data hasil baca AI dibuka saat diperlukan. Navigasi utama hanya Persiapan, Dokumentasi, Periksa laporan, dan PDF. Pemeriksaan akhir menyajikan daftar kekurangan dengan tombol menuju lokasi masalah.

Opsi ini memberi panduan bagi pemula sekaligus menjaga kecepatan dokumentasi berulang. Perubahan lebih besar daripada A, tetapi tidak mengharuskan backend AI atau penulisan ulang penyimpanan dan generator laporan.

## Kriteria penerimaan redesign

- Kondisi belum memiliki laporan menampilkan tindakan Buat laporan baru yang jelas.
- Alur normal tidak mengharuskan mengetik JSON, model ID, atau lokasi executable jika dapat dideteksi.
- Screenshot, penjelasan, dan status langkah aktif memiliki konteks yang sama.
- Setiap tahap memiliki satu tindakan utama yang relevan dan penjelasan prasyarat di dekatnya.
- AI opsional; dokumentasi manual tetap tersedia saat belum login atau layanan gagal.
- Status login, akses model, draf, pemeriksaan, tersimpan, dan kesiapan PDF dibedakan.
- Masalah kelengkapan memiliki tautan tindakan langsung untuk memperbaikinya.
- Tampilan diuji pada 1280×720, 1366×768 dan skala Windows 125%/150%.

Opsi C dipilih dan diterapkan setelah audit: beranda, persiapan terpandu, editor dua panel, formulir tugas modul, pemeriksaan dengan tombol Perbaiki, dan halaman PDF. Validasi meliputi 37 pengujian otomatis, smoke test penyimpanan/watcher/respons AI lama, serta render antarmuka pada skala 100%, 125%, dan 150%. Pengujian pengguna awam dan pengujian di mesin Windows bersih masih belum dilakukan.

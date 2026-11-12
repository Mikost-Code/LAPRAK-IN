import i18n from "i18next";
import { initReactI18next } from "react-i18next";

const id = {
  app: { name: "Laprak", tagline: "Template, dokumentasi, narasi" },
  nav: { home: "Beranda", setup: "Persiapan", template: "Template", docs: "Dokumentasi", review: "Periksa", pdf: "PDF", ai: "Profil AI", logout: "Keluar" },
  common: {
    save: "Simpan", saving: "Menyimpan…", saved: "Tersimpan", cancel: "Batal", delete: "Hapus", add: "Tambah", back: "Kembali", next: "Lanjut",
    loading: "Memuat…", retry: "Coba lagi", close: "Tutup", edit: "Ubah", apply: "Terapkan", done: "Selesai", open: "Buka", yes: "Ya", no: "Tidak",
    confirmDelete: "Hapus {{what}}? Tindakan ini tidak bisa dibatalkan.", error: "Terjadi kesalahan", none: "Belum ada",
    language: "Bahasa", indonesian: "Indonesia", english: "Inggris", optional: "opsional",
  },
  login: {
    title: "Masuk ke Laprak", body: "Proyek, template, dan gambar tersimpan di akun Anda. AI dipanggil dari browser ke 9Router atau provider pilihan Anda; server tidak pernah melihat percakapan AI.",
    google: "Masuk dengan Google", dev: "Masuk pengembang (tanpa Google)", devEmail: "Email pengembang", googleOff: "Login Google belum dikonfigurasi di server ini.",
  },
  home: {
    title: "Proyek laporan", subtitle: "Satu proyek untuk satu laporan. Template, dokumentasi, dan hasil PDF tersimpan bersama.",
    newProject: "Proyek baru", empty: "Belum ada proyek. Mulai dengan membuat proyek baru.", titleLabel: "Judul laporan", reportLang: "Bahasa laporan",
    updated: "Diperbarui {{when}}", steps: "{{count}} langkah", openProject: "Buka proyek",
  },
  setup: {
    title: "Persiapan", subtitle: "Identitas mengikuti slot template. Pilih profil AI yang akan dipakai browser Anda.",
    identity: "Identitas laporan", identityHint: "Kolom muncul dari pemetaan template. Tanpa template, isi kolom umum berikut.",
    aiProfile: "Profil AI untuk proyek ini", noProfile: "Belum ada profil AI. Buat di menu Profil AI.", manual: "Tanpa AI (tulis manual)",
    addField: "Tambah kolom", fieldKey: "Kunci", fieldValue: "Nilai",
  },
  template: {
    title: "Template", subtitle: "Unggah template LaTeX (ZIP). Template DOCX akan dikonversi otomatis pada tahap berikutnya.",
    upload: "Unggah ZIP template", replace: "Ganti template", drop: "Lepaskan ZIP di sini atau klik untuk memilih",
    status: { uploaded: "Perlu pemetaan slot", mapped: "Siap dipakai", verified: "Terverifikasi", failed: "Gagal" },
    slots: "Pemetaan slot", slotsHint: "Tentukan berkas utama, engine, perintah identitas, dan berkas tempat tiap bagian ditulis.",
    main: "Berkas utama", engine: "Engine", identityCommands: "Perintah identitas", identityHint: "Nama perintah LaTeX → kunci identitas (name, nim, title, …).",
    identityInputs: "\\input identitas yang diganti", marker: "Penanda alternatif", sectionSlots: "Slot bagian", slotKey: "Kunci", slotFile: "Berkas", slotHeading: "Judul bagian",
    documentationRequired: "Slot documentation wajib ada.", files: "Berkas .tex dalam template", preview: "Lihat isi", saveSlots: "Simpan pemetaan",
    none: "Belum ada template.", requiredAssets: "Aset wajib",
  },
  docs: {
    title: "Dokumentasi", subtitle: "Susun langkah, tempatkan gambar, lalu tulis atau buat draf deskripsi.",
    steps: "Langkah", addStep: "Tambah langkah", newStepTitle: "Langkah baru", unassigned: "Belum ditempatkan", dropImages: "Lepaskan gambar di sini atau klik untuk mengunggah",
    uploading: "Mengunggah {{count}} gambar…", skipped: "{{count}} gambar dilewati (duplikat).",
    stepTitle: "Judul langkah", instruction: "Instruksi / tujuan", notes: "Catatan Anda", narrative: "Deskripsi", caption: "Keterangan gambar",
    result: "Hasil", results: { unknown: "Belum diketahui", success: "Berhasil", failed: "Gagal", partial: "Sebagian" },
    notApplicable: "Alasan tidak berlaku", facts: "Fakta terbaca", noFacts: "Belum ada fakta.", factReviewed: "Diperiksa",
    review: "Tandai sudah diperiksa", unreview: "Batalkan periksa", reviewed: "Sudah diperiksa", draft: "Draf",
    aiAnalyze: "Baca gambar dengan AI", aiDescribe: "Buat draf deskripsi", aiMatch: "Tempatkan gambar dengan AI", aiRunning: "AI sedang bekerja…",
    aiNeedProfile: "Pilih profil AI di Persiapan untuk memakai fitur ini.", aiKeptYours: "Tulisan Anda dipertahankan; hasil AI tersimpan di riwayat draf.",
    aiApplied: "Draf AI diterapkan.", drafts: "Riwayat draf", applyDraft: "Pakai draf ini", noDrafts: "Belum ada draf.",
    moveTo: "Pindah ke langkah", images: "{{count}} gambar", noImages: "Belum ada gambar pada langkah ini.", deleteStep: "Hapus langkah",
    matchHint: "AI mengusulkan penempatan untuk {{count}} gambar. Periksa lalu terapkan.", applyMatches: "Terapkan usulan", confidence: "keyakinan {{pct}}%",
    selectStep: "Pilih langkah di kiri atau tambah langkah baru.",
  },
  review: {
    title: "Periksa laporan", subtitle: "Semua kekurangan tercantum di sini. Bagian naratif dibuat dari langkah yang sudah diperiksa.",
    blockers: "Kekurangan", clean: "Tidak ada kekurangan. Laporan siap dibangun.", fix: "Perbaiki", sections: "Bagian naratif",
    aiDraft: "Buat draf dengan AI", approveAll: "Setujui semua bagian", approved: "Bagian sudah disetujui", sectionReviewed: "Disetujui",
  },
  pdf: {
    title: "PDF", subtitle: "Kompilasi berjalan di server. Hasil final terkunci sampai semua kekurangan selesai.",
    build: "Bangun pratinjau", buildFinal: "Simpan PDF final", building: "Sedang dikompilasi…", stale: "Lebih lama dari data terbaru", latest: "Terbaru",
    noBuilds: "Belum ada hasil kompilasi.", log: "Log compiler", error: "Kesalahan", download: "Unduh PDF", compilerMissing: "Compiler LaTeX tidak tersedia di server.",
    compilerOk: "Compiler: {{version}}",
  },
  ai: {
    title: "Profil AI", subtitle: "Browser Anda yang memanggil provider. API key disimpan terenkripsi per akun dan hanya dikirim ke browser Anda saat dipakai.",
    add: "Tambah profil", name: "Nama", baseUrl: "Base URL", textModel: "Model teks", visionModel: "Model gambar (kosong = sama)", mode: "Mode keluaran",
    modes: { json_object: "JSON object", json_schema: "JSON schema", prompt: "Prompt saja" }, apiKey: "API key", apiKeyKeep: "Kosongkan untuk mempertahankan key lama",
    hasKey: "Key tersimpan", noKey: "Tanpa key", test: "Uji koneksi", testVision: "Uji juga kemampuan gambar", testing: "Menguji…",
    textOk: "Teks OK", visionOk: "Gambar OK", untested: "Belum diuji", routerHint: "9Router: biarkan base URL localhost dan pastikan CORS untuk origin ini diizinkan di 9Router.",
    localNote: "Panggilan ke localhost dari halaman ini mungkin meminta izin \"akses jaringan lokal\" di browser. Izinkan sekali.",
  },
};

type Dict = typeof id;

const en: Dict = {
  app: { name: "Laprak", tagline: "Template, documentation, narrative" },
  nav: { home: "Home", setup: "Setup", template: "Template", docs: "Documentation", review: "Review", pdf: "PDF", ai: "AI profiles", logout: "Sign out" },
  common: {
    save: "Save", saving: "Saving…", saved: "Saved", cancel: "Cancel", delete: "Delete", add: "Add", back: "Back", next: "Next",
    loading: "Loading…", retry: "Retry", close: "Close", edit: "Edit", apply: "Apply", done: "Done", open: "Open", yes: "Yes", no: "No",
    confirmDelete: "Delete {{what}}? This cannot be undone.", error: "Something went wrong", none: "None yet",
    language: "Language", indonesian: "Indonesian", english: "English", optional: "optional",
  },
  login: {
    title: "Sign in to Laprak", body: "Projects, templates and images live in your account. AI is called from your browser to 9Router or a provider you choose; the server never sees AI traffic.",
    google: "Sign in with Google", dev: "Developer sign-in (no Google)", devEmail: "Developer email", googleOff: "Google sign-in is not configured on this server.",
  },
  home: {
    title: "Report projects", subtitle: "One project per report. Template, documentation and PDF output stay together.",
    newProject: "New project", empty: "No projects yet. Start by creating one.", titleLabel: "Report title", reportLang: "Report language",
    updated: "Updated {{when}}", steps: "{{count}} steps", openProject: "Open project",
  },
  setup: {
    title: "Setup", subtitle: "Identity follows the template slots. Pick the AI profile your browser will use.",
    identity: "Report identity", identityHint: "Fields come from the template mapping. Without a template, fill the generic fields below.",
    aiProfile: "AI profile for this project", noProfile: "No AI profile yet. Create one under AI profiles.", manual: "No AI (write manually)",
    addField: "Add field", fieldKey: "Key", fieldValue: "Value",
  },
  template: {
    title: "Template", subtitle: "Upload a LaTeX template (ZIP). DOCX templates will be converted automatically in a later phase.",
    upload: "Upload template ZIP", replace: "Replace template", drop: "Drop the ZIP here or click to choose",
    status: { uploaded: "Needs slot mapping", mapped: "Ready", verified: "Verified", failed: "Failed" },
    slots: "Slot mapping", slotsHint: "Set the main file, engine, identity commands and the file each section is written to.",
    main: "Main file", engine: "Engine", identityCommands: "Identity commands", identityHint: "LaTeX command name → identity key (name, nim, title, …).",
    identityInputs: "Identity \\input lines to replace", marker: "Fallback marker", sectionSlots: "Section slots", slotKey: "Key", slotFile: "File", slotHeading: "Heading",
    documentationRequired: "The documentation slot is required.", files: ".tex files in the template", preview: "View", saveSlots: "Save mapping",
    none: "No template yet.", requiredAssets: "Required assets",
  },
  docs: {
    title: "Documentation", subtitle: "Arrange steps, place images, then write or draft descriptions.",
    steps: "Steps", addStep: "Add step", newStepTitle: "New step", unassigned: "Unplaced", dropImages: "Drop images here or click to upload",
    uploading: "Uploading {{count}} images…", skipped: "{{count}} images skipped (duplicates).",
    stepTitle: "Step title", instruction: "Instruction / goal", notes: "Your notes", narrative: "Description", caption: "Image caption",
    result: "Result", results: { unknown: "Unknown", success: "Success", failed: "Failed", partial: "Partial" },
    notApplicable: "Reason not applicable", facts: "Extracted facts", noFacts: "No facts yet.", factReviewed: "Reviewed",
    review: "Mark as reviewed", unreview: "Undo review", reviewed: "Reviewed", draft: "Draft",
    aiAnalyze: "Read images with AI", aiDescribe: "Draft description", aiMatch: "Place images with AI", aiRunning: "AI is working…",
    aiNeedProfile: "Choose an AI profile in Setup to use this.", aiKeptYours: "Your text was kept; the AI result is in the draft history.",
    aiApplied: "AI draft applied.", drafts: "Draft history", applyDraft: "Use this draft", noDrafts: "No drafts yet.",
    moveTo: "Move to step", images: "{{count}} images", noImages: "No images in this step yet.", deleteStep: "Delete step",
    matchHint: "AI proposed placements for {{count}} images. Review then apply.", applyMatches: "Apply proposals", confidence: "confidence {{pct}}%",
    selectStep: "Select a step on the left or add a new one.",
  },
  review: {
    title: "Review report", subtitle: "Everything still missing is listed here. Narrative sections are built from reviewed steps.",
    blockers: "Issues", clean: "Nothing missing. The report is ready to build.", fix: "Fix", sections: "Narrative sections",
    aiDraft: "Draft with AI", approveAll: "Approve all sections", approved: "Sections approved", sectionReviewed: "Approved",
  },
  pdf: {
    title: "PDF", subtitle: "Compilation runs on the server. The final output stays locked until all issues are resolved.",
    build: "Build preview", buildFinal: "Save final PDF", building: "Compiling…", stale: "Older than latest data", latest: "Latest",
    noBuilds: "No builds yet.", log: "Compiler log", error: "Error", download: "Download PDF", compilerMissing: "No LaTeX compiler available on the server.",
    compilerOk: "Compiler: {{version}}",
  },
  ai: {
    title: "AI profiles", subtitle: "Your browser calls the provider. API keys are stored encrypted per account and only sent to your browser when used.",
    add: "Add profile", name: "Name", baseUrl: "Base URL", textModel: "Text model", visionModel: "Vision model (empty = same)", mode: "Output mode",
    modes: { json_object: "JSON object", json_schema: "JSON schema", prompt: "Prompt only" }, apiKey: "API key", apiKeyKeep: "Leave empty to keep the stored key",
    hasKey: "Key stored", noKey: "No key", test: "Test connection", testVision: "Also test vision", testing: "Testing…",
    textOk: "Text OK", visionOk: "Vision OK", untested: "Untested", routerHint: "9Router: keep the localhost base URL and allow CORS for this origin in 9Router.",
    localNote: "Calling localhost from this page may trigger a browser \"local network access\" prompt. Allow it once.",
  },
};

i18n.use(initReactI18next).init({
  resources: { id: { translation: id }, en: { translation: en } },
  lng: (() => {
    try {
      return localStorage.getItem("laprak.locale") || "id";
    } catch {
      return "id";
    }
  })(),
  fallbackLng: "id",
  interpolation: { escapeValue: false },
});

export function setLocale(locale: "id" | "en") {
  i18n.changeLanguage(locale);
  try {
    localStorage.setItem("laprak.locale", locale);
  } catch {
    /* private mode */
  }
}

export default i18n;

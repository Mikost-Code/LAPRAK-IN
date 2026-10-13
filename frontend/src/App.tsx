import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle,
  FilePdf,
  FileText,
  FolderOpen,
  Gear,
  House,
  Images,
  Plus,
  Sparkle,
  WarningCircle,
  X,
  FloppyDisk,
  ClockCounterClockwise,
  Trash,
  ArrowsOut,
  DownloadSimple,
  Notebook,
  SidebarSimple,
} from "@phosphor-icons/react";
import {
  connect,
  rpc,
  type State,
  type Step,
  type ModuleDraft,
  type Project,
} from "./bridge";

type Page = "home" | "setup" | "editor" | "review" | "pdf";
type Run = (method: string, params?: unknown) => Promise<unknown>;
const sectionNames: Record<string, string> = {
  summary: "Rangkuman",
  theory: "Dasar teori",
  tools: "Alat dan bahan",
  tasks: "Tugas",
  references: "Referensi",
  discussion: "Pembahasan",
  conclusion: "Kesimpulan",
};
function Button({
  children,
  onClick,
  primary = false,
  disabled = false,
  className = "",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  primary?: boolean;
  disabled?: boolean;
  className?: string;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      className={`button ${primary ? "primary" : ""} ${className}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
function Tag({
  children,
  good = false,
}: {
  children: ReactNode;
  good?: boolean;
}) {
  return (
    <span className={`tag ${good ? "good" : ""}`}>
      {good ? <CheckCircle size={14} /> : <span className="status-dot" />}
      {children}
    </span>
  );
}
function Heading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className={wide ? "modal wide" : "modal"}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Tutup">
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}

export default function App() {
  const [state, setState] = useState<State>();
  const [page, setPage] = useState<Page>("home");
  const [toast, setToast] = useState("");
  const [fatal, setFatal] = useState("");
  const [modal, setModal] = useState<
    "new" | "identity" | "settings" | "module" | "sections" | "jobs" | null
  >(null);
  const [waiting, setWaiting] = useState(0);
  const [dirtyEditor, setDirtyEditor] = useState(false);
  const beforeNavigate = useRef<(() => Promise<void>) | null>(null);
  useEffect(() => {
    connect(setState, setToast).catch((error) => setFatal(error.message));
  }, []);
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [page]);
  useEffect(() => {
    window.laprakFlush = () => {
      void (async () => {
        await window.laprakDraftFlush?.();
        await beforeNavigate.current?.();
        await rpc("closeApp");
      })().catch((error) => setToast(error.message));
    };
    return () => {
      delete window.laprakFlush;
    };
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 8000);
    return () => clearTimeout(timer);
  }, [toast]);
  const run: Run = useCallback(async (method, params = {}) => {
    setWaiting((v) => v + 1);
    try {
      return await rpc(method, params);
    } catch (error) {
      setToast((error as Error).message);
      throw error;
    } finally {
      setWaiting((v) => v - 1);
    }
  }, []);
  const act = (method: string, params?: unknown) => {
    void run(method, params).catch(() => {});
  };
  const navigate = async (next: Page) => {
    try {
      await beforeNavigate.current?.();
      setPage(next);
    } catch {}
  };
  if (fatal)
    return (
      <div className="startup">
        <WarningCircle size={36} />
        <h1>Laprak belum terhubung</h1>
        <p>{fatal}</p>
      </div>
    );
  if (!state)
    return (
      <div className="startup">
        <div className="brand-mark">L</div>
        <h1>Menyiapkan ruang kerja…</h1>
        <p>Membuka data laporan lokal.</p>
      </div>
    );
  const project = state.project;
  const busy = waiting > 0 || state.busy.length > 0;
  const pages: { id: Page; title: string; icon: typeof House }[] = [
    { id: "home", title: "Beranda", icon: House },
    { id: "setup", title: "Persiapan", icon: Notebook },
    { id: "editor", title: "Dokumentasi", icon: Images },
    { id: "review", title: "Periksa laporan", icon: CheckCircle },
    { id: "pdf", title: "PDF laporan", icon: FilePdf },
  ];
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            void navigate("home");
          }}
        >
          <span className="brand-mark">L</span>
          <span>
            laprak<span className="brand-period">.</span>
          </span>
        </a>
        <div className="sidebar-label">RUANG KERJA</div>
        <nav>
          {pages.map(({ id, title, icon: Icon }) => (
            <button
              key={id}
              className={`nav-item ${page === id ? "active" : ""}`}
              disabled={id !== "home" && !project}
              onClick={() => void navigate(id)}
            >
              <Icon size={20} weight={page === id ? "fill" : "regular"} />
              {title}
              {id === "review" && !!project?.blockers.length && (
                <span className="nav-count">{project.blockers.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-note">
            <span className="status-dot" />
            <div>
              <strong>Disimpan di perangkat</strong>
              <small>Modul dan laporan tetap lokal</small>
            </div>
          </div>
          <button className="nav-item" onClick={() => setModal("settings")}>
            <Gear size={20} />
            Pengaturan
          </button>
        </div>
      </aside>
      <section className="app-main">
        <header className="topbar">
          <div className="breadcrumb">
            Laporan praktikum<span>/</span>
            <strong>{project?.identity.title || "Ruang kerja baru"}</strong>
          </div>
          <div className="topbar-right">
            {busy || dirtyEditor ? (
              <span className="saving">
                <span className="spinner" />
                {dirtyEditor ? "Menyimpan perubahan" : "Sedang memproses"}
              </span>
            ) : (
              <span className="saving">
                <Check size={15} />
                Tersimpan lokal
              </span>
            )}
            <span className="avatar" aria-label="Inisial pengguna">
              {(project?.identity.name || "L").slice(0, 1).toUpperCase()}
            </span>
          </div>
        </header>
        <main>
          {page === "home" && (
            <>
              <Heading
                eyebrow="LAPORAN PRAKTIKUM"
                title="Dari praktikum ke laporan yang rapi."
                description="Satu tempat untuk modul, bukti pekerjaan, dan penjelasanmu."
              />
              <div className="welcome-card">
                <div>
                  <Tag good>Siap untuk mulai</Tag>
                  <h2>
                    Kerjakan praktikumnya.
                    <br />
                    Susun laporannya di sini.
                  </h2>
                  <p>
                    Mulai dari modul, tambahkan screenshot, lalu periksa isi
                    sebelum menyimpan PDF.
                  </p>
                  <div className="button-row">
                    <Button primary onClick={() => setModal("new")}>
                      <Plus size={18} />
                      Buat laporan baru
                    </Button>
                    <Button
                      onClick={() => {
                        void run("openReport")
                          .then((path) => {
                            if (path) setPage("editor");
                          })
                          .catch(() => {});
                      }}
                    >
                      <FolderOpen size={18} />
                      Buka dari folder
                    </Button>
                  </div>
                </div>
                <div className="report-illustration" aria-hidden="true">
                  <div className="paper">
                    <span className="paper-label">LAPORAN PRAKTIKUM</span>
                    <div className="paper-title">
                      Jaringan
                      <br />
                      Komputer
                    </div>
                    <div className="paper-line" />
                    <div className="paper-line short" />
                    <div className="paper-evidence">
                      <FileText size={32} weight="duotone" />
                      <span>Bukti & penjelasan</span>
                    </div>
                    <div className="paper-line" />
                    <div className="paper-line short" />
                  </div>
                  <span className="illustration-check">
                    <Check size={22} weight="bold" />
                  </span>
                </div>
              </div>
              <div className="section-heading">
                <div>
                  <h2>Lanjutkan laporan</h2>
                  <p>Pekerjaan terakhir, tersimpan di perangkat ini.</p>
                </div>
                <Button
                  className="text-button"
                  onClick={() => act("importProject")}
                >
                  <FolderOpen size={16} />
                  Impor proyek ZIP
                </Button>
              </div>
              {state.recent.length ? (
                <div className="recent-grid">
                  {state.recent.map((recent) => (
                    <button
                      className="recent-card"
                      key={recent.path}
                      onClick={() => {
                        void run("openReport", { path: recent.path })
                          .then(() => setPage("editor"))
                          .catch(() => {});
                      }}
                    >
                      <span className="file-tile">
                        <FileText size={24} />
                      </span>
                      <div>
                        <h3>{recent.name}</h3>
                        <p title={recent.path}>{recent.path}</p>
                      </div>
                      <ArrowRight size={18} />
                    </button>
                  ))}
                </div>
              ) : (
                <div className="empty-recent">
                  <ClockCounterClockwise size={25} />
                  <div>
                    <strong>Belum ada laporan sebelumnya</strong>
                    <p>Laporan yang kamu buat akan muncul di sini.</p>
                  </div>
                </div>
              )}
              <div className="workflow-overview">
                {[
                  "Siapkan modul",
                  "Dokumentasikan bukti",
                  "Periksa penjelasan",
                  "Simpan PDF",
                ].map((title, i) => (
                  <div key={title}>
                    <span>{i + 1}</span>
                    {title}
                    {i < 3 && <ArrowRight size={16} />}
                  </div>
                ))}
              </div>
            </>
          )}
          {page === "setup" && project && (
            <Setup
              state={state}
              run={run}
              open={setModal}
              start={() => setPage("editor")}
            />
          )}
          {page === "editor" && project && (
            <Editor
              state={state}
              run={run}
              beforeNavigate={beforeNavigate}
              openSettings={() => setModal("settings")}
              onDirty={setDirtyEditor}
            />
          )}
          {page === "review" && project && (
            <>
              <Heading
                eyebrow="PEMERIKSAAN AKHIR"
                title="Pastikan laporan sesuai pekerjaanmu."
                description="Temukan bagian yang masih perlu dilengkapi. Hasil pengujian gagal tetap boleh dilaporkan sesuai bukti."
                action={
                  <Tag good={!project.blockers.length}>
                    {project.blockers.length
                      ? `${project.blockers.length} perlu diperiksa`
                      : "Pemeriksaan lengkap"}
                  </Tag>
                }
              />
              <div className="review-list">
                {project.blockers.length ? (
                  project.blockers.map((issue, i) => (
                    <div className="issue" key={i}>
                      <span className="issue-icon">
                        <WarningCircle size={21} />
                      </span>
                      <div>
                        <strong>{issue}</strong>
                        <small>
                          Lengkapi atau periksa sumber sebelum menyimpan PDF
                          final.
                        </small>
                      </div>
                      <Button
                        onClick={() => {
                          const step = project.steps.find((s) =>
                            issue.startsWith(s.title + ":"),
                          );
                          if (step) {
                            void run("selectStep", { id: step.id })
                              .then(() => setPage("editor"))
                              .catch(() => {});
                          } else if (issue.includes("modul")) {
                            setPage("setup");
                            if (project.module.name) setModal("module");
                          } else if (issue.includes("Instruksi"))
                            setPage("editor");
                          else setModal("sections");
                        }}
                      >
                        Perbaiki
                        <ArrowRight size={16} />
                      </Button>
                    </div>
                  ))
                ) : (
                  <div className="success-panel">
                    <CheckCircle size={32} />
                    <h2>Semua pemeriksaan selesai</h2>
                    <p>
                      Buat pratinjau PDF dari revisi terbaru sebelum menyimpan
                      hasil final.
                    </p>
                  </div>
                )}
              </div>
              <div className="page-footer">
                <Button onClick={() => setModal("sections")}>
                  <FileText size={18} />
                  Edit bagian laporan
                </Button>
                <Button primary onClick={() => setPage("pdf")}>
                  Lanjut ke PDF
                  <ArrowRight size={18} />
                </Button>
              </div>
            </>
          )}
          {page === "pdf" && project && (
            <>
              <Heading
                eyebrow="HASIL LAPORAN"
                title="Lihat hasilnya sebelum disimpan."
                description="Pratinjau mengikuti revisi terakhir yang dibuat. Isi laporan tetap perlu kamu periksa."
                action={
                  <Tag good={state.compilerReady}>
                    {state.compilerReady
                      ? "Pembuat PDF siap"
                      : "PDF belum siap"}
                  </Tag>
                }
              />
              <div className="pdf-toolbar">
                <div className="button-row">
                  <Button onClick={() => act("checkPdf")} disabled={busy}>
                    Periksa kesiapan PDF
                  </Button>
                  <Button
                    primary
                    onClick={() => act("buildPdf")}
                    disabled={!state.compilerReady || busy}
                  >
                    <FilePdf size={18} />
                    Buat pratinjau
                  </Button>
                </div>
                <div className="button-row">
                  <Button onClick={() => act("exportProject")}>
                    Ekspor proyek ZIP
                  </Button>
                  <Button
                    onClick={() => act("exportPdf")}
                    disabled={
                      !project.pdfUrl ||
                      project.build.revision !== project.revision ||
                      !!project.blockers.length
                    }
                  >
                    <DownloadSimple size={18} />
                    Simpan PDF final
                  </Button>
                </div>
              </div>
              {state.setupStatus && (
                <div className="info-banner">{state.setupStatus}</div>
              )}
              {project.pdfUrl &&
                project.build.revision !== project.revision && (
                  <div className="warning-banner">
                    Pratinjau belum memuat perubahan terakhir. Buat ulang
                    pratinjau untuk memperbaruinya.
                  </div>
                )}
              {project.blockers.length > 0 && (
                <div className="info-banner">
                  Masih ada {project.blockers.length} pemeriksaan untuk PDF
                  final.
                  <button onClick={() => setPage("review")}>
                    Lihat pemeriksaan
                    <ArrowRight size={14} />
                  </button>
                </div>
              )}
              <div className="pdf-preview">
                {project.pdfUrl ? (
                  <>
                    <iframe
                      title="Pratinjau PDF laporan"
                      src={project.pdfUrl + "#toolbar=0"}
                    />
                    <Button onClick={() => act("openPdf")}>
                      Buka PDF di aplikasi lain
                      <ArrowsOut size={16} />
                    </Button>
                  </>
                ) : (
                  <div className="empty-state">
                    <span className="large-file">
                      <FilePdf size={45} />
                    </span>
                    <h2>Pratinjau PDF akan tampil di sini</h2>
                    <p>
                      Periksa kesiapan PDF, lalu buat pratinjau dari laporanmu.
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </main>
        <footer className="statusbar">
          <span>
            {project
              ? `${project.steps.length} langkah · ${project.images.length} screenshot`
              : "Laprak · ruang kerja laporan lokal"}
          </span>
          <button onClick={() => setModal("jobs")}>
            Antrean AI{" "}
            {project?.jobs.filter((j) =>
              ["queued", "running", "failed", "interrupted"].includes(j.status),
            ).length || 0}
            <ArrowRight size={13} />
          </button>
        </footer>
      </section>
      {state.busy.length > 0 && (
        <div className="operation">
          <span className="spinner" />
          <span>{state.operation || state.busy[0]}</span>
          <button onClick={() => act("cancel")}>Batalkan</button>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          <WarningCircle size={19} />
          <span>{toast}</span>
          <button onClick={() => setToast("")} aria-label="Tutup pemberitahuan">
            <X size={18} />
          </button>
        </div>
      )}
      {(modal === "new" || modal === "identity") && (
        <IdentityForm
          initial={modal === "identity" ? project?.identity : undefined}
          close={() => setModal(null)}
          submit={async (identity) => {
            const value = await run(
              modal === "new" ? "createReport" : "saveIdentity",
              modal === "new" ? { identity } : identity,
            );
            if (value) {
              setModal(null);
              setPage("setup");
            }
          }}
        />
      )}
      {modal === "settings" && (
        <Settings state={state} run={run} close={() => setModal(null)} />
      )}
      {modal === "module" && project && (
        <ModuleForm project={project} run={run} close={() => setModal(null)} />
      )}
      {modal === "sections" && project && (
        <Sections project={project} run={run} close={() => setModal(null)} />
      )}
      {modal === "jobs" && (
        <Modal title="Antrean AI" onClose={() => setModal(null)}>
          <div className="modal-body">
            {project?.jobs.length ? (
              project.jobs.map((job) => (
                <div className="job" key={job.id}>
                  <strong>
                    {job.kind === "analyze_module"
                      ? "Membaca modul"
                      : "Menyusun penjelasan"}
                  </strong>
                  <Tag good={job.status === "succeeded"}>{job.status}</Tag>
                  <p>{job.error}</p>
                  {["failed", "cancelled", "interrupted"].includes(
                    job.status,
                  ) && (
                    <Button onClick={() => act("retryJob", { id: job.id })}>
                      Coba ulang
                    </Button>
                  )}
                </div>
              ))
            ) : (
              <p>
                Belum ada proses AI. Kamu dapat menulis laporan secara manual.
              </p>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

function Setup({
  state,
  run,
  open,
  start,
}: {
  state: State;
  run: Run;
  open: (modal: "identity" | "module" | "settings") => void;
  start: () => void;
}) {
  const [index, setIndex] = useState(0);
  const p = state.project!;
  const act = (method: string) => {
    void run(method).catch(() => {});
  };
  const items = [
    "Identitas",
    "Modul praktikum",
    "Template PDF",
    "AI & screenshot",
  ];
  return (
    <>
      <Heading
        eyebrow="PERSIAPAN LAPORAN"
        title="Siapkan sekali. Lanjutkan dengan tenang."
        description="Mulai dari identitas dan modul. AI serta screenshot otomatis bisa diatur nanti."
      />
      <div className="setup-stepper">
        {items.map((title, i) => (
          <button
            className={index === i ? "current" : ""}
            key={title}
            onClick={() => setIndex(i)}
          >
            <span>{i + 1}</span>
            {title}
          </button>
        ))}
      </div>
      <div className="setup-card">
        {index === 0 && (
          <>
            <span className="section-icon">
              <Notebook size={28} />
            </span>
            <h2>Siapa dan apa yang dilaporkan?</h2>
            <p>
              Identitas ini dipakai pada sampul laporan. Kamu bisa mengubahnya
              kapan saja.
            </p>
            <dl className="identity-summary">
              <div>
                <dt>Judul praktikum</dt>
                <dd>{p.identity.title}</dd>
              </div>
              <div>
                <dt>Mahasiswa</dt>
                <dd>{p.identity.name || "Belum diisi"}</dd>
              </div>
              <div>
                <dt>NIM / kelas</dt>
                <dd>
                  {p.identity.nim || "—"} / {p.identity.class || "—"}
                </dd>
              </div>
              <div>
                <dt>Mata kuliah</dt>
                <dd>{p.identity.course || "Jaringan Komputer"}</dd>
              </div>
            </dl>
            <Button onClick={() => open("identity")}>Ubah identitas</Button>
          </>
        )}
        {index === 1 && (
          <>
            <span className="section-icon">
              <FileText size={28} />
            </span>
            <h2>Mulai dari panduan praktikum.</h2>
            <p>
              Unggah modul PDF, lalu periksa tugas yang perlu didokumentasikan.
              Modul adalah panduan, bukan bukti pekerjaan.
            </p>
            <div className="upload-zone">
              <FilePdf size={36} />
              <strong>{p.module.name || "Tambahkan modul praktikum"}</strong>
              <span>
                {p.module.pages?.length
                  ? `${p.module.pages.length} halaman · ${p.moduleReviewed ? "tugas sudah diperiksa" : "tugas belum diperiksa"}`
                  : "Pilih PDF dari perangkatmu"}
              </span>
              <Button
                primary
                onClick={() => act("uploadModule")}
                disabled={!!state.busy.length}
              >
                {p.module.name ? "Ganti modul PDF" : "Pilih modul PDF"}
                <Plus size={16} />
              </Button>
            </div>
            {p.module.name && (
              <div className="button-row">
                <Button onClick={() => open("module")}>
                  Periksa daftar tugas
                  <ArrowRight size={16} />
                </Button>
                <Button onClick={() => act("viewModule")}>Lihat modul</Button>
              </div>
            )}
          </>
        )}
        {index === 2 && (
          <>
            <span className="section-icon">
              <FilePdf size={28} />
            </span>
            <h2>Gunakan format laporanmu.</h2>
            <p>
              Pilih folder template LaTeX. Aplikasi memeriksa pembuat PDF
              sebelum laporan dikompilasi.
            </p>
            <div className="setting-summary">
              <span>Template laporan</span>
              <strong>
                {String(
                  state.settings.template || "Template di folder template",
                )}
              </strong>
            </div>
            <div className="button-row">
              <Button onClick={() => act("chooseTemplate")}>
                <FolderOpen size={18} />
                Pilih template
              </Button>
              <Button
                primary
                onClick={() => act("checkPdf")}
                disabled={!!state.busy.length}
              >
                Periksa kesiapan PDF
              </Button>
            </div>
            {state.setupStatus && (
              <div className="info-banner">{state.setupStatus}</div>
            )}
            <p className="helper">
              Belum siap? Dokumentasi tetap bisa dikerjakan. Pengaturan engine
              dan executable tersedia di Pengaturan.
            </p>
          </>
        )}
        {index === 3 && (
          <>
            <span className="section-icon">
              <Sparkle size={28} />
            </span>
            <h2>Bantuan AI, saat kamu membutuhkannya.</h2>
            <p>
              Login GPT lewat browser untuk membantu membaca bukti dan membuat
              draf. Kamu juga bisa menulis seluruh laporan secara manual.
            </p>
            <div className="connection-card">
              <div>
                <strong>
                  {state.settings.model
                    ? "GPT / AI telah dipilih"
                    : "Belum ada AI terhubung"}
                </strong>
                <span>
                  {state.aiTested.vision
                    ? "Teks dan gambar sudah diuji"
                    : state.aiTested.text
                      ? "Teks sudah diuji"
                      : state.settings.model
                        ? "Kemampuan model belum diuji"
                        : "Tidak perlu API key untuk login GPT"}
                </span>
              </div>
              <div className="button-row">
                <Button
                  primary
                  onClick={() => act("connectGpt")}
                  disabled={!!state.busy.length}
                >
                  <Sparkle size={16} />
                  Hubungkan GPT
                </Button>
                {!!state.settings.model && (
                  <Button
                    onClick={() => act("testAi")}
                    disabled={!!state.busy.length}
                  >
                    Periksa kemampuan
                  </Button>
                )}
              </div>
            </div>
            {state.operation && (
              <div className="info-banner">{state.operation}</div>
            )}
            <div className="setting-summary">
              <div>
                <strong>
                  Screenshot otomatis <span className="optional">Opsional</span>
                </strong>
                <p>
                  {state.watching
                    ? "Folder sedang dipantau"
                    : p.folder ||
                      "Pilih folder untuk mengimpor screenshot saat file baru masuk."}
                </p>
              </div>
              <Button onClick={() => act("chooseFolder")}>
                <FolderOpen size={17} />
                Pilih folder
              </Button>
            </div>
            <Button className="text-button" onClick={() => open("settings")}>
              Gunakan provider AI lain
              <ArrowRight size={16} />
            </Button>
          </>
        )}
      </div>
      <div className="page-footer">
        <Button
          onClick={() => setIndex(Math.max(0, index - 1))}
          disabled={index === 0}
        >
          <ArrowLeft size={17} />
          Kembali
        </Button>
        <Button
          primary
          onClick={() => (index === 3 ? start() : setIndex(index + 1))}
        >
          {index === 3 ? "Mulai dokumentasi" : "Lanjut"}
          <ArrowRight size={17} />
        </Button>
      </div>
    </>
  );
}

function IdentityForm({
  initial,
  close,
  submit,
}: {
  initial?: Record<string, string>;
  close: () => void;
  submit: (identity: Record<string, string>) => Promise<void>;
}) {
  const [values, setValues] = useState<Record<string, string>>({
    ...{
      name: "",
      nim: "",
      class: "",
      course: "Jaringan Komputer",
      title: "",
      date: new Date().toLocaleDateString("en-CA"),
      meeting: "1",
    },
    ...initial,
  });
  const [saving, setSaving] = useState(false);
  return (
    <Modal
      title={initial ? "Identitas laporan" : "Buat laporan baru"}
      onClose={close}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setSaving(true);
          void submit(values)
            .catch(() => {})
            .finally(() => setSaving(false));
        }}
      >
        <div className="modal-body">
          <p className="helper">
            Isi identitas utama. Lokasi penyimpanan dipilih setelah ini;
            aplikasi membuat folder laporan tersendiri.
          </p>
          <div className="form-grid">
            {[
              ["title", "Judul praktikum"],
              ["name", "Nama mahasiswa"],
              ["nim", "NIM"],
              ["class", "Kelas"],
              ["course", "Mata kuliah"],
              ["date", "Tanggal"],
              ["meeting", "Pertemuan"],
            ].map(([key, text]) => (
              <label className={key === "title" ? "span-two" : ""} key={key}>
                {text}
                <input
                  required={key === "title"}
                  type={key === "date" ? "date" : "text"}
                  value={values[key] || ""}
                  onChange={(e) =>
                    setValues({ ...values, [key]: e.target.value })
                  }
                />
              </label>
            ))}
          </div>
          <details>
            <summary>Identitas tambahan sesuai template</summary>
            <div className="form-grid">
              {[
                ["month_year", "Bulan dan tahun"],
                ["assistant_a", "Asisten 1"],
                ["assistant_b", "Asisten 2"],
                ["members", "Anggota kelompok"],
              ].map(([key, text]) => (
                <label key={key}>
                  {text}
                  <textarea
                    value={values[key] || ""}
                    onChange={(e) =>
                      setValues({ ...values, [key]: e.target.value })
                    }
                  />
                </label>
              ))}
            </div>
          </details>
        </div>
        <div className="modal-footer">
          <Button onClick={close}>Batal</Button>
          <Button primary type="submit" disabled={saving}>
            {saving
              ? "Menyimpan…"
              : initial
                ? "Simpan identitas"
                : "Lanjut · pilih lokasi"}
            <ArrowRight size={17} />
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function Editor({
  state,
  run,
  beforeNavigate,
  openSettings,
  onDirty,
}: {
  state: State;
  run: Run;
  beforeNavigate: React.MutableRefObject<(() => Promise<void>) | null>;
  openSettings: () => void;
  onDirty: (dirty: boolean) => void;
}) {
  const p = state.project!;
  const step = p.steps.find((s) => s.id === state.active) || p.steps[0];
  const [newStep, setNewStep] = useState(false);
  const [title, setTitle] = useState("");
  return (
    <>
      <Heading
        eyebrow="DOKUMENTASI PRAKTIKUM"
        title="Bukti dan cerita dari pekerjaanmu."
        description="Pilih langkah, tambahkan screenshot, lalu jelaskan apa yang benar-benar dilakukan."
        action={
          <Button
            onClick={() => {
              setNewStep(true);
            }}
          >
            <Plus size={17} />
            Tambah langkah
          </Button>
        }
      />
      {newStep && (
        <Modal
          title="Tambah langkah praktikum"
          onClose={() => setNewStep(false)}
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void (async () => {
                await beforeNavigate.current?.();
                await run("addStep", { title });
                setNewStep(false);
                setTitle("");
              })().catch(() => {});
            }}
          >
            <div className="modal-body">
              <label>
                Judul langkah
                <input
                  autoFocus
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Contoh: Uji koneksi antar-PC"
                />
              </label>
            </div>
            <div className="modal-footer">
              <Button onClick={() => setNewStep(false)}>Batal</Button>
              <Button primary type="submit">
                Tambahkan langkah
                <Plus size={17} />
              </Button>
            </div>
          </form>
        </Modal>
      )}
      <div className="editor-layout">
        <aside className="steps-panel">
          <div className="steps-heading">
            <strong>Langkah praktikum</strong>
            <span>{p.steps.length}</span>
          </div>
          {p.steps.map((s, i) => (
            <button
              key={s.id}
              className={`step-item ${s.id === step?.id ? "selected" : ""}`}
              onClick={() => {
                void (async () => {
                  await beforeNavigate.current?.();
                  await run("selectStep", { id: s.id });
                })().catch(() => {});
              }}
            >
              <span className={`step-number ${s.reviewed ? "complete" : ""}`}>
                {s.reviewed ? (
                  <Check size={16} />
                ) : (
                  String(i + 1).padStart(2, "0")
                )}
              </span>
              <span>
                <strong>{s.title}</strong>
                <small>
                  {s.reviewed
                    ? "Selesai diperiksa"
                    : `${p.images.filter((e) => e.step_id === s.id).length} screenshot · draf`}
                </small>
              </span>
            </button>
          ))}
          <div className="steps-bottom">
            <FileText size={17} />
            {p.moduleReviewed
              ? "Panduan modul sudah diperiksa"
              : "Modul belum diperiksa"}
          </div>
        </aside>
        {step ? (
          <StepEditor
            key={step.id}
            step={step}
            project={p}
            state={state}
            run={run}
            beforeNavigate={beforeNavigate}
            openSettings={openSettings}
            onDirty={onDirty}
          />
        ) : (
          <div className="empty-state">
            <Images size={36} />
            <h2>Tambahkan langkah praktikum</h2>
            <p>Setiap langkah menyimpan screenshot dan penjelasannya.</p>
          </div>
        )}
      </div>
    </>
  );
}

function StepEditor({
  step,
  project: p,
  state,
  run,
  beforeNavigate,
  openSettings,
  onDirty,
}: {
  step: Step;
  project: Project;
  state: State;
  run: Run;
  beforeNavigate: React.MutableRefObject<(() => Promise<void>) | null>;
  openSettings: () => void;
  onDirty: (dirty: boolean) => void;
}) {
  const [draft, setDraft] = useState(step);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    onDirty(dirty || saving);
    return () => onDirty(false);
  }, [dirty, saving, onDirty]);
  const [selected, setSelected] = useState("");
  const [history, setHistory] = useState(false);
  const [checks, setChecks] = useState(step.checks);
  const [imageTool, setImageTool] = useState<"crop" | "resize" | null>(null);
  const [zoomImage, setZoomImage] = useState(false);
  const [transform, setTransform] = useState({
    x: "0",
    y: "0",
    width: "100",
    height: "100",
    maximum: "1600",
  });
  const images = p.images.filter((e) => e.step_id === step.id);
  const image = images.find((e) => e.id === selected) || images[0];
  const savingPromise = useRef<Promise<void> | null>(null);
  const draftRef = useRef(draft);
  const dirtyRef = useRef(false);
  const generation = useRef(0);
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, []);
  useEffect(() => {
    if (!dirtyRef.current) {
      draftRef.current = step;
      setDraft(step);
      setChecks(step.checks);
    }
  }, [step.revision]);
  const update = (changes: Partial<Step>) => {
    generation.current++;
    draftRef.current = { ...draftRef.current, ...changes };
    dirtyRef.current = true;
    setDraft(draftRef.current);
    setDirty(true);
    setChecks([false, false]);
  };
  const save = useCallback(async () => {
    if (savingPromise.current) await savingPromise.current;
    while (dirtyRef.current) {
      const number = generation.current;
      const data = draftRef.current;
      setSaving(true);
      const promise = run("saveStep", {
        id: data.id,
        title: data.title,
        notes: data.notes,
        narrative: data.narrative,
        facts: data.facts,
        result: data.result,
        instruction_ids: data.instruction_ids,
        not_applicable: data.not_applicable,
      })
        .then(() => {
          if (generation.current === number) {
            dirtyRef.current = false;
            setDirty(false);
          }
        })
        .finally(() => {
          setSaving(false);
          savingPromise.current = null;
        });
      savingPromise.current = promise;
      await promise;
    }
  }, [run]);
  useEffect(() => {
    beforeNavigate.current = save;
    return () => {
      beforeNavigate.current = null;
    };
  }, [save]);
  useEffect(() => {
    if (!dirty) return;
    const timer = setTimeout(() => void save().catch(() => {}), 900);
    return () => clearTimeout(timer);
  }, [draft, dirty, save]);
  const act = (method: string, params?: unknown) => {
    void (async () => {
      await save();
      await run(method, params);
    })().catch(() => {});
  };
  const canApprove =
    !!draft.not_applicable.trim() ||
    (!!images.length &&
      !!draft.narrative.trim() &&
      checks.every(Boolean) &&
      draft.facts.every((f) => f.reviewed));
  return (
    <article className="step-editor">
      <div className="step-title">
        <div>
          <span className="eyebrow">LANGKAH AKTIF</span>
          <input
            aria-label="Judul langkah aktif"
            value={draft.title}
            onChange={(e) => update({ title: e.target.value })}
          />
        </div>
        <Tag good={step.reviewed}>
          {step.reviewed
            ? "Selesai"
            : dirty || saving
              ? "Menyimpan…"
              : "Draf tersimpan"}
        </Tag>
      </div>
      <div className="evidence-block">
        <div className="section-heading compact">
          <h3>Screenshot pekerjaan</h3>
          <Button onClick={() => act("importImages")}>
            <Plus size={16} />
            Tambahkan screenshot
          </Button>
        </div>
        <div className={`image-canvas ${!image ? "empty" : ""}`}>
          {image ? (
            <img
              src={image.url}
              alt={image.name}
              onLoad={(event) => {
                const width = event.currentTarget.naturalWidth;
                const height = event.currentTarget.naturalHeight;
                setTransform((old) => ({
                  ...old,
                  width: String(width),
                  height: String(height),
                }));
              }}
            />
          ) : (
            <div>
              <Images size={36} />
              <strong>Tambahkan bukti untuk langkah ini</strong>
              <p>PNG atau JPEG dari praktikum yang kamu kerjakan.</p>
            </div>
          )}
        </div>
        {images.length > 0 && (
          <div className="image-strip">
            {images.map((e) => (
              <button
                key={e.id}
                className={image?.id === e.id ? "selected" : ""}
                onClick={() => setSelected(e.id)}
              >
                <img src={e.url} alt="" />
                <span>{e.name}</span>
              </button>
            ))}
          </div>
        )}
        {image && (
          <div className="image-actions">
            <span>{image.name}</span>
            <Button className="text-button" onClick={() => setZoomImage(true)}>
              <ArrowsOut size={14} />
              Perbesar
            </Button>
            <Button
              className="text-button"
              onClick={() => setImageTool("crop")}
            >
              Potong salinan
            </Button>
            <Button
              className="text-button"
              onClick={() => setImageTool("resize")}
            >
              Ubah ukuran
            </Button>
            <Button
              className="text-button"
              onClick={() =>
                act("imageTool", { id: image.id, tool: "restore" })
              }
            >
              Pulihkan asli
            </Button>
            <button
              className="icon-button"
              aria-label="Hapus screenshot dari laporan"
              onClick={() => {
                if (
                  confirm(
                    "Hapus screenshot ini dari laporan? Gambar asli tetap disimpan.",
                  )
                )
                  act("changeImage", { id: image.id, remove: true });
              }}
            >
              <Trash size={17} />
            </button>
          </div>
        )}
      </div>
      {image && (
        <details>
          <summary>Urutan dan penempatan screenshot</summary>
          <div className="button-row">
            <Button
              onClick={() => act("changeImage", { id: image.id, offset: -1 })}
            >
              Geser ke kiri
            </Button>
            <Button
              onClick={() => act("changeImage", { id: image.id, offset: 1 })}
            >
              Geser ke kanan
            </Button>
          </div>
          <label>
            Pindah ke langkah
            <select
              value={image.step_id}
              onChange={(e) =>
                act("changeImage", { id: image.id, target: e.target.value })
              }
            >
              {p.steps.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
          </label>
        </details>
      )}
      <label className="field-label">
        Catatan pekerjaan <span className="optional">Opsional</span>
        <input
          placeholder="Contoh: ping gagal sebelum routing ditambahkan"
          value={draft.notes}
          onChange={(e) => update({ notes: e.target.value })}
        />
      </label>
      <div className="narrative-heading">
        <div>
          <h3>Penjelasan langkah</h3>
          <p>Tulis tindakan, tujuan, dan hasil sesuai bukti.</p>
        </div>
        <Button
          onClick={() =>
            state.settings.model ? act("analyzeStep") : openSettings()
          }
          disabled={!!state.busy.length}
        >
          <Sparkle size={17} />
          {state.settings.model ? "Bantu buat draf" : "Hubungkan AI"}
        </Button>
      </div>
      <textarea
        className="narrative-input"
        placeholder="Apa yang kamu lakukan? Apa hasil yang terlihat?"
        aria-label="Penjelasan langkah"
        value={draft.narrative}
        onChange={(e) => update({ narrative: e.target.value })}
      />
      <div className="result-row">
        <label>
          Hasil pengujian
          <select
            value={draft.result}
            onChange={(e) => update({ result: e.target.value })}
          >
            {["belum diketahui", "sukses", "gagal", "sebagian sukses"].map(
              (v) => (
                <option key={v}>{v}</option>
              ),
            )}
          </select>
        </label>
        <Button className="text-button" onClick={() => setHistory(true)}>
          <ClockCounterClockwise size={17} />
          Riwayat draf
        </Button>
      </div>
      {!!draft.unknown?.length && (
        <div className="warning-banner">
          <strong>Masih belum jelas dari bukti:</strong>
          <ul>
            {draft.unknown.map((value, index) => (
              <li key={index}>{value}</li>
            ))}
          </ul>
        </div>
      )}
      <details className="facts-details">
        <summary>
          Data yang terbaca <span>{draft.facts.length} nilai</span>
        </summary>
        <p className="helper">
          Koreksi nilai dan tandai hanya jika sudah sesuai screenshot.
        </p>
        {draft.facts.map((fact, i) => (
          <div className="fact-row" key={i}>
            <input
              aria-label="Jenis data"
              value={fact.type}
              onChange={(e) =>
                update({
                  facts: draft.facts.map((f, j) =>
                    j === i ? { ...f, type: e.target.value } : f,
                  ),
                })
              }
            />
            <input
              aria-label="Nilai data"
              value={fact.value}
              onChange={(e) =>
                update({
                  facts: draft.facts.map((f, j) =>
                    j === i
                      ? { ...f, value: e.target.value, reviewed: false }
                      : f,
                  ),
                })
              }
            />
            <input
              aria-label="Sumber data"
              value={fact.source}
              onChange={(e) =>
                update({
                  facts: draft.facts.map((f, j) =>
                    j === i ? { ...f, source: e.target.value } : f,
                  ),
                })
              }
            />
            <label className="checkbox">
              <input
                type="checkbox"
                checked={fact.reviewed}
                onChange={(e) =>
                  update({
                    facts: draft.facts.map((f, j) =>
                      j === i ? { ...f, reviewed: e.target.checked } : f,
                    ),
                  })
                }
              />
              Sesuai
            </label>
            <button
              className="icon-button"
              aria-label="Hapus data"
              onClick={() =>
                update({ facts: draft.facts.filter((_, j) => j !== i) })
              }
            >
              <Trash size={16} />
            </button>
          </div>
        ))}
        <Button
          onClick={() =>
            update({
              facts: [
                ...draft.facts,
                { type: "", value: "", source: "", reviewed: false },
              ],
            })
          }
        >
          <Plus size={15} />
          Tambah data
        </Button>
      </details>
      <details className="facts-details">
        <summary>
          Tugas modul yang terkait{" "}
          <span>{draft.instruction_ids.length} tugas</span>
        </summary>
        {p.instructions.length ? (
          p.instructions.map((task) => (
            <label key={task.id} className="checkbox task-check">
              <input
                type="checkbox"
                checked={draft.instruction_ids.includes(task.id)}
                onChange={(e) =>
                  update({
                    instruction_ids: e.target.checked
                      ? [...draft.instruction_ids, task.id]
                      : draft.instruction_ids.filter((id) => id !== task.id),
                  })
                }
              />
              <span>
                {task.description}
                <small>Halaman PDF {task.page}</small>
              </span>
            </label>
          ))
        ) : (
          <p>
            Periksa modul pada halaman Persiapan untuk menambahkan panduan
            tugas.
          </p>
        )}
      </details>
      <div className="approval-card">
        <h3>Periksa sebelum menandai selesai</h3>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={checks[0]}
            onChange={(e) => setChecks([e.target.checked, checks[1]])}
          />
          Fakta dan alamat tujuan sesuai bukti.
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={checks[1]}
            onChange={(e) => setChecks([checks[0], e.target.checked])}
          />
          Hasil pengujian dan penjelasan sudah saya periksa.
        </label>
        <div className="approval-footer">
          <span>
            {canApprove
              ? "Siap ditandai selesai."
              : "Lengkapi bukti, penjelasan, data, dan kedua pemeriksaan."}
          </span>
          <Button
            primary
            disabled={!canApprove || saving}
            onClick={() =>
              act("approveStep", {
                id: step.id,
                checks,
                snapshot: {
                  narrative: draft.narrative,
                  facts: draft.facts,
                  evidenceIds: images.map((e) => e.id),
                },
              })
            }
          >
            <Check size={17} />
            Tandai selesai
          </Button>
        </div>
      </div>
      <details>
        <summary>Langkah tidak berlaku pada praktikum ini</summary>
        <label>
          Alasan
          <textarea
            value={draft.not_applicable}
            onChange={(e) => update({ not_applicable: e.target.value })}
            placeholder="Jelaskan mengapa langkah ini tidak berlaku."
          />
        </label>
      </details>
      <details>
        <summary>Ubah urutan langkah</summary>
        <div className="button-row">
          <Button
            disabled={p.steps[0]?.id === step.id}
            onClick={() => {
              const ids = p.steps.map((s) => s.id);
              const index = ids.indexOf(step.id);
              [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]];
              act("reorderSteps", { ids });
            }}
          >
            Geser ke atas
          </Button>
          <Button
            disabled={p.steps[p.steps.length - 1]?.id === step.id}
            onClick={() => {
              const ids = p.steps.map((s) => s.id);
              const index = ids.indexOf(step.id);
              [ids[index + 1], ids[index]] = [ids[index], ids[index + 1]];
              act("reorderSteps", { ids });
            }}
          >
            Geser ke bawah
          </Button>
        </div>
      </details>
      {imageTool && image && (
        <Modal
          title={
            imageTool === "crop"
              ? "Potong salinan screenshot"
              : "Ubah ukuran screenshot"
          }
          onClose={() => setImageTool(null)}
        >
          <div className="modal-body">
            <p className="helper">
              Gambar asli tetap tersimpan. Ukuran dan koordinat memakai piksel
              gambar yang sedang ditampilkan.
            </p>
            <div className="form-grid">
              {(imageTool === "crop"
                ? [
                    ["x", "Posisi X"],
                    ["y", "Posisi Y"],
                    ["width", "Lebar"],
                    ["height", "Tinggi"],
                  ]
                : [["maximum", "Sisi maksimum (px)"]]
              ).map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    inputMode="numeric"
                    type="text"
                    value={transform[key as keyof typeof transform]}
                    onChange={(e) =>
                      setTransform({ ...transform, [key]: e.target.value })
                    }
                  />
                </label>
              ))}
            </div>
          </div>
          <div className="modal-footer">
            <Button onClick={() => setImageTool(null)}>Batal</Button>
            <Button
              primary
              onClick={() => {
                act("imageTransform", {
                  id: image.id,
                  ...(imageTool === "crop"
                    ? {
                        rect: [
                          Number(transform.x),
                          Number(transform.y),
                          Number(transform.width),
                          Number(transform.height),
                        ],
                      }
                    : { maximum: Number(transform.maximum) }),
                });
                setImageTool(null);
              }}
            >
              Buat salinan
              <Check size={17} />
            </Button>
          </div>
        </Modal>
      )}
      {zoomImage && image && (
        <Modal title={image.name} onClose={() => setZoomImage(false)} wide>
          <div className="zoom-canvas">
            <img src={image.url} alt={image.name} />
          </div>
        </Modal>
      )}
      {history && (
        <Modal
          title="Riwayat draf langkah"
          onClose={() => setHistory(false)}
          wide
        >
          <div className="modal-body">
            {p.revisions[step.id]?.length ? (
              p.revisions[step.id].map((revision, i) => (
                <div className="revision" key={i}>
                  <strong>
                    {revision.data.origin === "AI"
                      ? "Draf AI"
                      : "Revisi tulisanmu"}
                  </strong>
                  <small>
                    {revision.created.slice(0, 19).replace("T", " ")}
                  </small>
                  <p>{revision.data.narrative || "Belum ada penjelasan."}</p>
                  <Button
                    onClick={() => {
                      if (
                        confirm(
                          "Terapkan revisi ini menggantikan penjelasan sekarang? Tulisan sekarang akan disimpan dalam riwayat.",
                        )
                      ) {
                        act("applyRevision", { id: step.id, index: i });
                        setHistory(false);
                      }
                    }}
                  >
                    Periksa dan gunakan draf ini
                  </Button>
                </div>
              ))
            ) : (
              <p>Belum ada revisi tersimpan.</p>
            )}
          </div>
        </Modal>
      )}
    </article>
  );
}

function ModuleForm({
  project: p,
  run,
  close,
}: {
  project: Project;
  run: Run;
  close: () => void;
}) {
  const base: ModuleDraft = {
    objectives: [],
    theory: "",
    tools: [],
    instructions: [],
    unknown_pages:
      p.module.pages?.filter((p) => p.needs_vision).map((p) => p.page) || [],
    ...p.moduleDraft,
  };
  const [data, setData] = useState(base);
  const [dirty, setDirty] = useState(false);
  const [source, setSource] = useState(
    p.moduleManual ||
      p.module.pages
        ?.map((page) => `[Halaman file ${page.page}]\n${page.text}`)
        .join("\n\n") ||
      "",
  );
  const [createSteps, setCreateSteps] = useState(
    p.steps.length === 1 && !p.images.length && !p.steps[0].narrative,
  );
  const [tab, setTab] = useState("tasks");
  const [submitting, setSubmitting] = useState(false);
  useEffect(() => {
    window.laprakDraftFlush = () =>
      dirty ? run("draftModule", { data, source }) : Promise.resolve();
    return () => {
      window.laprakDraftFlush = null;
    };
  }, [data, source, dirty, run]);
  const edit = (next: ModuleDraft) => {
    setData(next);
    setDirty(true);
  };
  useEffect(() => {
    if (!dirty) return;
    const timer = setTimeout(
      () => void run("draftModule", { data, source }).catch(() => {}),
      900,
    );
    return () => clearTimeout(timer);
  }, [data, source, dirty, run]);
  const finish = async () => {
    try {
      if (dirty) await run("draftModule", { data, source });
      close();
    } catch {}
  };
  return (
    <Modal title="Periksa tugas dari modul" onClose={() => void finish()} wide>
      <div className="modal-body">
        <p className="helper">
          Tugas ini menjadi panduan dokumentasi. Periksa isi dan nomor halaman
          sebelum digunakan.
        </p>
        <div className="tabs">
          {[
            ["tasks", "Daftar tugas"],
            ["summary", "Ringkasan"],
            ["source", "Teks modul"],
          ].map(([key, text]) => (
            <button
              className={tab === key ? "selected" : ""}
              key={key}
              onClick={() => setTab(key)}
            >
              {text}
            </button>
          ))}
        </div>
        {Object.keys(p.modulePending).length > 0 && (
          <div className="info-banner">
            Draf AI tersedia untuk diperiksa.
            <button onClick={() => edit({ ...base, ...p.modulePending })}>
              Gunakan draf AI
              <ArrowRight size={15} />
            </button>
          </div>
        )}
        {tab === "tasks" && (
          <>
            <div className="task-table-head">
              <span>Instruksi / tugas praktikum</span>
              <span>Halaman</span>
              <span />
            </div>
            {data.instructions.map((task, i) => (
              <div className="task-form-row" key={i}>
                <textarea
                  aria-label={`Tugas ${i + 1}`}
                  value={task.description}
                  onChange={(e) =>
                    edit({
                      ...data,
                      instructions: data.instructions.map((t, j) =>
                        j === i ? { ...t, description: e.target.value } : t,
                      ),
                    })
                  }
                />
                <input
                  type="text"
                  inputMode="numeric"
                  aria-label="Halaman PDF"
                  value={task.page}
                  onChange={(e) =>
                    edit({
                      ...data,
                      instructions: data.instructions.map((t, j) =>
                        j === i ? { ...t, page: Number(e.target.value) } : t,
                      ),
                    })
                  }
                />
                <button
                  className="icon-button"
                  aria-label="Hapus tugas"
                  onClick={() =>
                    edit({
                      ...data,
                      instructions: data.instructions.filter((_, j) => j !== i),
                    })
                  }
                >
                  <Trash size={18} />
                </button>
              </div>
            ))}
            {!data.instructions.length && (
              <div className="empty-recent">
                <FileText size={24} />
                <p>Tambahkan tugas dari modul atau gunakan bantuan AI.</p>
              </div>
            )}
            <Button
              onClick={() =>
                edit({
                  ...data,
                  instructions: [
                    ...data.instructions,
                    { description: "", page: 1, evidence: "" },
                  ],
                })
              }
            >
              <Plus size={16} />
              Tambah tugas
            </Button>
          </>
        )}
        {tab === "summary" && (
          <div className="form-grid single">
            {[
              ["objectives", "Tujuan (satu per baris)"],
              ["theory", "Dasar teori"],
              ["tools", "Alat dan bahan (satu per baris)"],
            ].map(([key, title]) => (
              <label key={key}>
                {title}
                <textarea
                  value={
                    key === "theory"
                      ? data.theory
                      : (data[key as "objectives" | "tools"] || []).join("\n")
                  }
                  onChange={(e) =>
                    edit({
                      ...data,
                      [key]:
                        key === "theory"
                          ? e.target.value
                          : e.target.value.split("\n"),
                    })
                  }
                />
              </label>
            ))}
          </div>
        )}
        {tab === "source" && (
          <label>
            Teks dari PDF
            <textarea
              className="source-input"
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setDirty(true);
              }}
            />
          </label>
        )}
        {base.unknown_pages.length > 0 && (
          <div className="warning-banner">
            <strong>Halaman belum terbaca</strong>
            {base.unknown_pages.map((number) => (
              <label className="checkbox" key={number}>
                <input
                  type="checkbox"
                  checked={!data.unknown_pages.includes(number)}
                  onChange={(e) =>
                    edit({
                      ...data,
                      unknown_pages: e.target.checked
                        ? data.unknown_pages.filter((p) => p !== number)
                        : [...data.unknown_pages, number],
                    })
                  }
                />
                Halaman PDF {number} sudah saya baca dan periksa.
              </label>
            ))}
          </div>
        )}
        <label className="checkbox">
          <input
            type="checkbox"
            checked={createSteps}
            onChange={(e) => setCreateSteps(e.target.checked)}
          />
          Buat langkah dokumentasi dari tugas yang belum dihubungkan.
        </label>
      </div>
      <div className="modal-footer">
        <Button
          onClick={() => {
            void (async () => {
              if (dirty) await run("draftModule", { data, source });
              await run("analyzeModule");
            })().catch(() => {});
          }}
        >
          <Sparkle size={17} />
          Bantu baca dengan AI
        </Button>
        <Button
          primary
          disabled={submitting}
          onClick={() => {
            setSubmitting(true);
            void (async () => {
              if (dirty) await run("draftModule", { data, source });
              return run("saveModule", { data, createSteps });
            })()
              .then(close)
              .catch(() => {})
              .finally(() => setSubmitting(false));
          }}
        >
          Gunakan sebagai panduan
          <Check size={17} />
        </Button>
      </div>
    </Modal>
  );
}

function Sections({
  project: p,
  run,
  close,
}: {
  project: Project;
  run: Run;
  close: () => void;
}) {
  const [values, setValues] = useState(p.sections);
  const [key, setKey] = useState("discussion");
  const [reviewed, setReviewed] = useState(p.sectionsReviewed);
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    window.laprakDraftFlush = () => run("saveSections", { values, reviewed });
    return () => {
      window.laprakDraftFlush = null;
    };
  }, [values, reviewed, run]);
  useEffect(() => {
    if (!dirty) return;
    const timer = setTimeout(
      () =>
        void run("saveSections", { values, reviewed: false }).catch(() => {}),
      900,
    );
    return () => clearTimeout(timer);
  }, [values, dirty, run]);
  return (
    <Modal
      title="Bagian laporan"
      onClose={() => {
        void run("saveSections", { values, reviewed })
          .then(close)
          .catch(() => {});
      }}
      wide
    >
      <div className="modal-body">
        <label>
          Bagian yang ingin diedit
          <select value={key} onChange={(e) => setKey(e.target.value)}>
            {Object.entries(sectionNames).map(([key, title]) => (
              <option value={key} key={key}>
                {title}
              </option>
            ))}
          </select>
        </label>
        {p.sectionDrafts[key] && (
          <div className="info-banner">
            Draf AI tersedia.
            <button
              onClick={() => {
                setValues({ ...values, [key]: p.sectionDrafts[key] });
                setDirty(true);
                setReviewed(false);
              }}
            >
              Gunakan draf ini
              <ArrowRight size={15} />
            </button>
          </div>
        )}
        <textarea
          className="section-input"
          aria-label={sectionNames[key]}
          value={values[key] || ""}
          onChange={(e) => {
            setValues({ ...values, [key]: e.target.value });
            setDirty(true);
            setReviewed(false);
          }}
          placeholder={`Tulis ${sectionNames[key].toLowerCase()} berdasarkan modul dan pekerjaan yang diperiksa.`}
        />
        <label className="checkbox">
          <input
            type="checkbox"
            checked={reviewed}
            onChange={(e) => setReviewed(e.target.checked)}
          />
          Semua bagian dan sumber sudah saya periksa.
        </label>
      </div>
      <div className="modal-footer">
        {["discussion", "conclusion"].includes(key) ? (
          <Button
            onClick={() => {
              void run("generateSection", { kind: key }).catch(() => {});
            }}
          >
            <Sparkle size={17} />
            Bantu buat draf
          </Button>
        ) : (
          <span />
        )}
        <Button
          primary
          onClick={() => {
            void run("saveSections", { values, reviewed })
              .then(close)
              .catch(() => {});
          }}
        >
          <FloppyDisk size={17} />
          Simpan bagian laporan
        </Button>
      </div>
    </Modal>
  );
}

function Settings({
  state,
  run,
  close,
}: {
  state: State;
  run: Run;
  close: () => void;
}) {
  const [config, setConfig] = useState({ ...state.settings });
  const [secret, setSecret] = useState("");
  useEffect(() => {
    setConfig((prev) => ({
      ...prev,
      provider: state.settings.provider,
      model: state.settings.model,
      endpoint: state.settings.endpoint,
      vision: state.settings.vision,
    }));
  }, [state.settings.model, state.settings.provider, state.settings.vision]);
  const change = (key: string, value: string | number | boolean) =>
    setConfig({ ...config, [key]: value });
  return (
    <Modal title="Pengaturan Laprak" onClose={close}>
      <div className="modal-body">
        <div className="settings-login">
          <span className="section-icon">
            <Sparkle size={24} />
          </span>
          <div>
            <h3>Hubungkan GPT lewat browser</h3>
            <p>Login tanpa API key. Setelah berhasil, kembali ke Laprak.</p>
          </div>
        </div>
        <div className="button-row">
          <Button
            primary
            onClick={() => {
              void run("connectGpt").catch(() => {});
            }}
            disabled={!!state.busy.length}
          >
            Hubungkan GPT
            <ArrowRight size={17} />
          </Button>
          <Button
            onClick={() => {
              void run("testAi").catch(() => {});
            }}
            disabled={!!state.busy.length || !state.settings.model}
          >
            Periksa kemampuan
          </Button>
        </div>
        {state.operation && (
          <div className="info-banner">{state.operation}</div>
        )}
        <details>
          <summary>Provider dan model lain</summary>
          <div className="form-grid single">
            <label>
              Provider
              <select
                value={String(config.provider || "GPT (login Codex)")}
                onChange={(e) => {
                  setSecret("");
                  setConfig({
                    ...config,
                    provider: e.target.value,
                    model: "",
                    vision: false,
                    endpoint:
                      e.target.value === "GPT (login Codex)"
                        ? "codex://local"
                        : e.target.value === "Ollama"
                          ? "http://localhost:11434"
                          : e.target.value === "OpenCode Zen (API)"
                            ? "https://opencode.ai/zen/v1"
                            : "https://api.openai.com/v1",
                  });
                }}
              >
                {[
                  "GPT (login Codex)",
                  "API kompatibel OpenAI",
                  "Ollama",
                  "OpenCode Zen (API)",
                ].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              Model
              <input
                value={String(config.model || "")}
                onChange={(e) => change("model", e.target.value)}
              />
            </label>
            {config.provider !== "GPT (login Codex)" && (
              <>
                <label>
                  Alamat API
                  <input
                    value={String(config.endpoint || "")}
                    onChange={(e) => change("endpoint", e.target.value)}
                  />
                </label>
                <label>
                  API key
                  <input
                    type="password"
                    autoComplete="off"
                    value={secret}
                    onChange={(e) => setSecret(e.target.value)}
                    placeholder="Kosong untuk memakai key yang tersimpan"
                  />
                </label>
              </>
            )}
            <label>
              Format respons
              <select
                value={String(config.structured || "Prompt JSON")}
                onChange={(e) => change("structured", e.target.value)}
              >
                {["JSON", "JSON schema", "Prompt JSON"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
          </div>
          <Button
            onClick={() => {
              void run("saveSettings", { ...config, secret })
                .then(() => setSecret(""))
                .catch(() => {});
            }}
          >
            Simpan koneksi
          </Button>
        </details>
        <details>
          <summary>Template dan pembuat PDF</summary>
          <div className="form-grid single">
            <label>
              Folder template
              <input
                value={String(config.template || "")}
                onChange={(e) => change("template", e.target.value)}
              />
            </label>
            <label>
              Engine
              <select
                value={String(config.engine || "xelatex")}
                onChange={(e) => change("engine", e.target.value)}
              >
                {["xelatex", "lualatex", "pdflatex"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              Lokasi executable
              <input
                value={String(config.compiler || "")}
                onChange={(e) => change("compiler", e.target.value)}
                placeholder="Ditemukan otomatis jika tersedia"
              />
            </label>
          </div>
        </details>
        <details>
          <summary>Analisis otomatis dan batas pemakaian</summary>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={!!config.auto}
              onChange={(e) => change("auto", e.target.checked)}
            />
            Analisis otomatis saat screenshot masuk
          </label>
          <div className="form-grid">
            {[
              ["timeout", "Waktu tunggu (detik)", 90],
              ["image_size", "Ukuran gambar (px)", 1600],
              ["max_jobs", "Batas antrean", 10],
              ["pdf_mb", "Ukuran modul (MB)", 50],
              ["pdf_pages", "Batas halaman PDF", 200],
            ].map(([key, title, fallback]) => (
              <label key={String(key)}>
                {title}
                <input
                  type="text"
                  inputMode="numeric"
                  value={String(config[String(key)] ?? fallback)}
                  onChange={(e) => change(String(key), Number(e.target.value))}
                />
              </label>
            ))}
          </div>
        </details>
      </div>
      <div className="modal-footer">
        <Button onClick={close}>Tutup</Button>
        <Button
          primary
          onClick={() => {
            void run("saveSettings", { ...config, secret })
              .then(close)
              .catch(() => {});
          }}
        >
          Simpan pengaturan
          <Check size={17} />
        </Button>
      </div>
    </Modal>
  );
}

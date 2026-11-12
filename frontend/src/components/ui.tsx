import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { CircleNotch, UploadSimple, X } from "@phosphor-icons/react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger"; busy?: boolean; icon?: ReactNode; small?: boolean };

export function Button({ variant, busy, icon, small, children, className = "", disabled, ...rest }: ButtonProps) {
  return (
    <button className={`button ${variant ?? ""} ${small ? "small" : ""} ${className}`} disabled={disabled || busy} {...rest}>
      {busy ? <CircleNotch size={16} className="spin" /> : icon}
      {children}
    </button>
  );
}

export function Tag({ tone = "muted", children }: { tone?: "good" | "warn" | "muted" | "bad"; children: ReactNode }) {
  return <span className={`tag ${tone}`}>{children}</span>;
}

export function Field({ label, hint, children, inline }: { label: ReactNode; hint?: ReactNode; children: ReactNode; inline?: boolean }) {
  return (
    <label className={`field ${inline ? "inline" : ""}`}>
      <span className="field-label">{label}</span>
      {children}
      {hint && <small className="field-hint">{hint}</small>}
    </label>
  );
}

export function Modal({ title, onClose, children, footer, wide }: { title: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true">
        <header>
          <h2>{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label="close"><X size={18} /></button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="button-row end">{footer}</footer>}
      </div>
    </div>
  );
}

export function Empty({ title, body, action }: { title: ReactNode; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {body && <p>{body}</p>}
      {action}
    </div>
  );
}

export const Spinner = ({ label }: { label?: string }) => (
  <div className="spinner"><CircleNotch size={20} className="spin" />{label}</div>
);

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="error-text" role="alert">{(error as Error).message ?? String(error)}</div>;
}

export function Dropzone({ onFiles, accept, multiple = true, children, compact }: { onFiles: (files: File[]) => void; accept: string; multiple?: boolean; children: ReactNode; compact?: boolean }) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  return (
    <div
      className={`dropzone ${over ? "over" : ""} ${compact ? "compact" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFiles(Array.from(e.dataTransfer.files)); }}
      onClick={() => input.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
    >
      <UploadSimple size={22} />
      <span>{children}</span>
      <input ref={input} type="file" hidden accept={accept} multiple={multiple}
        onChange={(e) => { onFiles(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
    </div>
  );
}

// ---- toasts (tiny global bus, no provider needed)
type Toast = { id: number; message: string; tone: "good" | "bad" | "muted" };
const listeners = new Set<(t: Toast) => void>();
let counter = 0;
export function notify(message: string, tone: Toast["tone"] = "muted") {
  listeners.forEach((l) => l({ id: ++counter, message, tone }));
}

export function Toasts() {
  const [items, setItems] = useState<Toast[]>([]);
  useEffect(() => {
    const add = (t: Toast) => {
      setItems((prev) => [...prev, t]);
      window.setTimeout(() => setItems((prev) => prev.filter((p) => p.id !== t.id)), 4500);
    };
    listeners.add(add);
    return () => { listeners.delete(add); };
  }, []);
  return (
    <div className="toasts" aria-live="polite">
      {items.map((t) => <div key={t.id} className={`toast ${t.tone}`}>{t.message}</div>)}
    </div>
  );
}

export function SaveIndicator({ state, error }: { state: string; error?: string | null }) {
  const label = { idle: "", dirty: "…", saving: "Menyimpan…", saved: "Tersimpan", error: error ?? "Gagal menyimpan" }[state] ?? "";
  return <span className={`save-indicator ${state}`}>{label}</span>;
}

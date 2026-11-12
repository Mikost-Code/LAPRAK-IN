import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Plus, Trash } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { Lang } from "../api/types";
import { useAutosave, useProfiles, useProjectCtx } from "../hooks";
import { Button, Field, SaveIndicator } from "../components/ui";

const GENERIC = ["name", "nim", "class", "title", "meeting", "month_year", "assistant_a", "assistant_b", "members"];
const LABELS: Record<Lang, Record<string, string>> = {
  id: { name: "Nama", nim: "NIM", class: "Kelas", title: "Judul", meeting: "Pertemuan", month_year: "Bulan/Tahun", assistant_a: "Asisten 1", assistant_b: "Asisten 2", members: "Anggota kelompok" },
  en: { name: "Name", nim: "Student ID", class: "Class", title: "Title", meeting: "Session", month_year: "Month/Year", assistant_a: "Assistant 1", assistant_b: "Assistant 2", members: "Group members" },
};

export default function Setup() {
  const { t } = useTranslation();
  const { project, refresh } = useProjectCtx();
  const profiles = useProfiles();
  const [form, setForm] = useState({ title: project.title, language: project.language, identity: { ...project.identity }, ai_profile_id: project.ai_profile_id });
  useEffect(() => {
    setForm({ title: project.title, language: project.language, identity: { ...project.identity }, ai_profile_id: project.ai_profile_id });
  }, [project.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = useAutosave(form, async (value) => {
    await api.patchProject(project.id, value);
    await refresh();
  });
  const keys = project.template ? Array.from(new Set(Object.values(project.template.slot_map.identity.commands))) : GENERIC;
  const extra = Object.keys(form.identity).filter((k) => !keys.includes(k));
  const labels = LABELS[form.language];
  const setIdentity = (key: string, value: string) => setForm((f) => ({ ...f, identity: { ...f.identity, [key]: value } }));
  const [newKey, setNewKey] = useState("");
  return (
    <div className="page">
      <div className="page-heading">
        <div><div className="eyebrow">{project.title}</div><h1>{t("setup.title")}</h1><p>{t("setup.subtitle")}</p></div>
        <SaveIndicator state={save.state} error={save.error} />
      </div>
      <div className="grid-2">
        <div className="card">
          <h2>{t("setup.identity")}</h2>
          <p>{t("setup.identityHint")}</p>
          <div className="form-grid">
            <Field label={t("home.titleLabel")}><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
            <Field label={t("home.reportLang")}>
              <select value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value as Lang })}>
                <option value="id">{t("common.indonesian")}</option><option value="en">{t("common.english")}</option>
              </select>
            </Field>
          </div>
          <div className="form-grid">
            {keys.map((key) => (
              <Field key={key} label={labels[key] ?? key}>
                {key === "members" ? (
                  <textarea value={form.identity[key] ?? ""} onChange={(e) => setIdentity(key, e.target.value)} />
                ) : (
                  <input value={form.identity[key] ?? ""} onChange={(e) => setIdentity(key, e.target.value)} />
                )}
              </Field>
            ))}
          </div>
          {extra.map((key) => (
            <div className="kv-row" key={key}>
              <strong>{key}</strong>
              <input value={form.identity[key]} onChange={(e) => setIdentity(key, e.target.value)} />
              <button className="icon-button" onClick={() => setForm((f) => { const identity = { ...f.identity }; delete identity[key]; return { ...f, identity }; })}><Trash size={16} /></button>
            </div>
          ))}
          <div className="kv-row">
            <input placeholder={t("setup.fieldKey")} value={newKey} onChange={(e) => setNewKey(e.target.value.replace(/[^a-zA-Z0-9_]/g, ""))} />
            <span />
            <Button small icon={<Plus size={14} />} disabled={!newKey || newKey in form.identity} onClick={() => { setIdentity(newKey, ""); setNewKey(""); }}>{t("setup.addField")}</Button>
          </div>
        </div>
        <div className="card">
          <h2>{t("setup.aiProfile")}</h2>
          {profiles.data?.length ? (
            <select value={form.ai_profile_id ?? ""} onChange={(e) => setForm({ ...form, ai_profile_id: e.target.value || null })}>
              <option value="">{t("setup.manual")}</option>
              {profiles.data.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.text_model || "?"}{p.vision_ok ? " · vision" : ""}</option>)}
            </select>
          ) : (
            <p>{t("setup.noProfile")}</p>
          )}
          <Link to="/ai" className="button">{t("nav.ai")}</Link>
        </div>
      </div>
    </div>
  );
}

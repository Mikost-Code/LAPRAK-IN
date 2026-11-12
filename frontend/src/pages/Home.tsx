import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Plus } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { Lang } from "../api/types";
import { timeAgo } from "../hooks";
import { Button, Empty, ErrorText, Field, Modal, Spinner } from "../components/ui";

export default function Home() {
  const { t, i18n } = useTranslation();
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const [creating, setCreating] = useState(false);
  const lang = (i18n.language as Lang) || "id";
  return (
    <div className="page">
      <div className="page-heading">
        <div><div className="eyebrow">{t("app.name")}</div><h1>{t("home.title")}</h1><p>{t("home.subtitle")}</p></div>
        <Button variant="primary" icon={<Plus size={16} weight="bold" />} onClick={() => setCreating(true)}>{t("home.newProject")}</Button>
      </div>
      {projects.isLoading && <Spinner />}
      <ErrorText error={projects.error} />
      {projects.data?.length === 0 && (
        <Empty title={t("common.none")} body={t("home.empty")} action={<Button onClick={() => setCreating(true)}>{t("home.newProject")}</Button>} />
      )}
      <div className="grid-cards">
        {projects.data?.map((p) => (
          <Link key={p.id} to={`/projects/${p.id}/docs`} className="card project-card">
            <h3>{p.title}</h3>
            <div className="meta">
              <span>{p.language.toUpperCase()}</span>
              <span>·</span>
              <span>{t("home.updated", { when: timeAgo(p.updated_at, lang) })}</span>
            </div>
            {p.identity.name && <p>{p.identity.name}</p>}
          </Link>
        ))}
      </div>
      {creating && <CreateModal onClose={() => setCreating(false)} />}
    </div>
  );
}

function CreateModal({ onClose }: { onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const client = useQueryClient();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState<Lang>((i18n.language as Lang) || "id");
  const [name, setName] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const project = await api.createProject({ title, language, identity: name ? { name, title } : { title } });
      await client.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}/setup`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  };
  return (
    <Modal title={t("home.newProject")} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>{t("common.cancel")}</Button><Button variant="primary" busy={busy} disabled={!title.trim()} onClick={submit}>{t("common.next")}</Button></>}>
      <Field label={t("home.titleLabel")}><input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
      <Field label={t("setup.identity") + " · " + t("common.optional")}><input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nama" /></Field>
      <Field label={t("home.reportLang")}>
        <select value={language} onChange={(e) => setLanguage(e.target.value as Lang)}>
          <option value="id">{t("common.indonesian")}</option>
          <option value="en">{t("common.english")}</option>
        </select>
      </Field>
      <ErrorText error={error} />
    </Modal>
  );
}

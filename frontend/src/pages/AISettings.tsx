import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle, Plus, Trash, XCircle } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { AIProfile } from "../api/types";
import { probeProfile } from "../ai/runner";
import { useProfiles } from "../hooks";
import { Button, Empty, ErrorText, Field, Modal, Tag, notify } from "../components/ui";

const BLANK: Partial<AIProfile> & { api_key?: string } = { name: "9Router", base_url: "http://localhost:20128/v1", text_model: "", vision_model: "", structured_mode: "json_object", api_key: "" };

export default function AISettings() {
  const { t } = useTranslation();
  const profiles = useProfiles();
  const [editing, setEditing] = useState<(Partial<AIProfile> & { api_key?: string }) | null>(null);
  return (
    <div className="page">
      <div className="page-heading">
        <div><div className="eyebrow">{t("app.name")}</div><h1>{t("ai.title")}</h1><p>{t("ai.subtitle")}</p></div>
        <Button variant="primary" icon={<Plus size={16} weight="bold" />} onClick={() => setEditing({ ...BLANK })}>{t("ai.add")}</Button>
      </div>
      <div className="note">{t("ai.routerHint")} {t("ai.localNote")}</div>
      {profiles.data?.length === 0 && <Empty title={t("common.none")} action={<Button onClick={() => setEditing({ ...BLANK })}>{t("ai.add")}</Button>} />}
      <div className="grid-cards">
        {profiles.data?.map((p) => <ProfileCard key={p.id} profile={p} onEdit={() => setEditing({ ...p, api_key: "" })} />)}
      </div>
      {editing && <ProfileModal initial={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function ProfileCard({ profile, onEdit }: { profile: AIProfile; onEdit: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [testing, setTesting] = useState(false);
  const [withVision, setWithVision] = useState(Boolean(profile.vision_model || profile.vision_ok));
  const [error, setError] = useState<unknown>(null);
  const test = async () => {
    setTesting(true);
    setError(null);
    try {
      const { api_key } = await api.profileSecret(profile.id);
      const result = await probeProfile({ ...profile, vision_ok: true }, api_key, withVision);
      await api.recordTest(profile.id, result.text, result.vision);
      await client.invalidateQueries({ queryKey: ["profiles"] });
      if (result.error) setError(new Error(result.error));
      notify(result.text ? t("ai.textOk") + (withVision ? (result.vision ? " · " + t("ai.visionOk") : " · vision ✗") : "") : "✗", result.text ? "good" : "bad");
    } catch (e) {
      setError(e);
      await api.recordTest(profile.id, false, false).catch(() => undefined);
      await client.invalidateQueries({ queryKey: ["profiles"] });
    } finally {
      setTesting(false);
    }
  };
  const remove = async () => {
    if (!window.confirm(t("common.confirmDelete", { what: profile.name }))) return;
    await api.deleteProfile(profile.id);
    await client.invalidateQueries({ queryKey: ["profiles"] });
  };
  return (
    <div className="card">
      <div className="card-title"><h3>{profile.name}</h3><button className="icon-button" onClick={remove}><Trash size={16} /></button></div>
      <p style={{ wordBreak: "break-all" }}>{profile.base_url}</p>
      <div className="button-row">
        <Tag tone="muted">{profile.text_model || "—"}</Tag>
        {profile.vision_model && <Tag tone="muted">vision: {profile.vision_model}</Tag>}
        <Tag tone={profile.has_api_key ? "good" : "muted"}>{profile.has_api_key ? t("ai.hasKey") : t("ai.noKey")}</Tag>
      </div>
      <div className="button-row">
        {profile.tested_at ? (
          <>
            <Tag tone={profile.text_ok ? "good" : "bad"}>{profile.text_ok ? <CheckCircle size={12} weight="fill" /> : <XCircle size={12} weight="fill" />}{t("ai.textOk")}</Tag>
            <Tag tone={profile.vision_ok ? "good" : "muted"}>{profile.vision_ok ? <CheckCircle size={12} weight="fill" /> : <XCircle size={12} />}{t("ai.visionOk")}</Tag>
          </>
        ) : <Tag tone="warn">{t("ai.untested")}</Tag>}
      </div>
      <label className="field inline"><input type="checkbox" checked={withVision} onChange={(e) => setWithVision(e.target.checked)} />{t("ai.testVision")}</label>
      <ErrorText error={error} />
      <div className="button-row">
        <Button busy={testing} onClick={test}>{testing ? t("ai.testing") : t("ai.test")}</Button>
        <Button variant="ghost" onClick={onEdit}>{t("common.edit")}</Button>
      </div>
    </div>
  );
}

function ProfileModal({ initial, onClose }: { initial: Partial<AIProfile> & { api_key?: string }; onClose: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [form, setForm] = useState(initial);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = { name: form.name, base_url: form.base_url, text_model: form.text_model, vision_model: form.vision_model, structured_mode: form.structured_mode, ...(form.api_key ? { api_key: form.api_key } : {}) };
      if (form.id) await api.patchProfile(form.id, body);
      else await api.createProfile(body);
      await client.invalidateQueries({ queryKey: ["profiles"] });
      onClose();
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  };
  return (
    <Modal title={form.id ? t("common.edit") : t("ai.add")} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>{t("common.cancel")}</Button><Button variant="primary" busy={busy} onClick={submit}>{t("common.save")}</Button></>}>
      <Field label={t("ai.name")}><input value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
      <Field label={t("ai.baseUrl")} hint={t("ai.routerHint")}><input value={form.base_url ?? ""} onChange={(e) => setForm({ ...form, base_url: e.target.value })} /></Field>
      <div className="form-grid">
        <Field label={t("ai.textModel")}><input value={form.text_model ?? ""} onChange={(e) => setForm({ ...form, text_model: e.target.value })} /></Field>
        <Field label={t("ai.visionModel")}><input value={form.vision_model ?? ""} onChange={(e) => setForm({ ...form, vision_model: e.target.value })} /></Field>
      </div>
      <Field label={t("ai.mode")}>
        <select value={form.structured_mode} onChange={(e) => setForm({ ...form, structured_mode: e.target.value as AIProfile["structured_mode"] })}>
          {(["json_object", "json_schema", "prompt"] as const).map((m) => <option key={m} value={m}>{t(`ai.modes.${m}`)}</option>)}
        </select>
      </Field>
      <Field label={t("ai.apiKey")} hint={form.id ? t("ai.apiKeyKeep") : undefined}>
        <input type="password" autoComplete="off" value={form.api_key ?? ""} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
      </Field>
      <ErrorText error={error} />
    </Modal>
  );
}

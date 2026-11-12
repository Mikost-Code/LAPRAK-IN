import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Trash } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { SlotMap } from "../api/types";
import { useProjectCtx } from "../hooks";
import { Button, Dropzone, ErrorText, Field, Modal, Tag, notify } from "../components/ui";

const SLOT_KEYS = ["documentation", "discussion", "conclusion", "theory", "tools", "tasks", "references", "summary"];
const IDENTITY_KEYS = ["name", "nim", "class", "title", "meeting", "month_year", "assistant_a", "assistant_b", "members"];

export default function TemplatePage() {
  const { t } = useTranslation();
  const { project, refresh } = useProjectCtx();
  const template = project.template;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [viewing, setViewing] = useState<{ path: string; content: string } | null>(null);
  const [map, setMap] = useState<SlotMap | null>(template?.slot_map ?? null);
  useEffect(() => setMap(template?.slot_map ?? null), [template?.id, template?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await api.uploadTemplate(project.id, file);
      await refresh();
      notify(t("common.saved"), "good");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const saveSlots = async () => {
    if (!map) return;
    setBusy(true);
    setError(null);
    try {
      await api.setSlots(project.id, map);
      await refresh();
      notify(t("common.saved"), "good");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const view = async (path: string) => setViewing(await api.templateFile(project.id, path));
  const tone = template?.status === "mapped" || template?.status === "verified" ? "good" : template?.status === "failed" ? "bad" : "warn";

  return (
    <div className="page">
      <div className="page-heading">
        <div><div className="eyebrow">{project.title}</div><h1>{t("template.title")}</h1><p>{t("template.subtitle")}</p></div>
        {template && <Tag tone={tone}>{t(`template.status.${template.status}`)}</Tag>}
      </div>
      <ErrorText error={error} />
      {!template ? (
        <Dropzone onFiles={upload} accept=".zip" multiple={false}>{busy ? t("common.loading") : t("template.drop")}</Dropzone>
      ) : (
        <>
          <div className="card">
            <div className="card-title">
              <div><h2>{template.name}</h2><p>{template.message}</p></div>
              <Dropzone onFiles={upload} accept=".zip" multiple={false} compact>{t("template.replace")}</Dropzone>
            </div>
            <div>
              <div className="field-label">{t("template.files")}</div>
              <div className="file-list">{template.files.map((f) => <Button key={f} small variant="ghost" onClick={() => view(f)}>{f}</Button>)}</div>
            </div>
          </div>
          {map && <SlotEditor map={map} files={template.files} onChange={setMap} />}
          <div className="button-row end">
            <Button variant="primary" busy={busy} onClick={saveSlots}>{t("template.saveSlots")}</Button>
          </div>
        </>
      )}
      {viewing && (
        <Modal title={viewing.path} onClose={() => setViewing(null)} wide>
          <pre className="code-view">{viewing.content}</pre>
        </Modal>
      )}
    </div>
  );
}

function SlotEditor({ map, files, onChange }: { map: SlotMap; files: string[]; onChange: (m: SlotMap) => void }) {
  const { t } = useTranslation();
  const [newCmd, setNewCmd] = useState("");
  const [newSlot, setNewSlot] = useState("discussion");
  const commands = Object.entries(map.identity.commands);
  const slots = Object.entries(map.slots);
  const setIdentity = (patch: Partial<SlotMap["identity"]>) => onChange({ ...map, identity: { ...map.identity, ...patch } });
  return (
    <div className="card">
      <h2>{t("template.slots")}</h2>
      <p>{t("template.slotsHint")}</p>
      <div className="form-grid">
        <Field label={t("template.main")}>
          <select value={map.main} onChange={(e) => onChange({ ...map, main: e.target.value })}>
            {files.map((f) => <option key={f}>{f}</option>)}
          </select>
        </Field>
        <Field label={t("template.engine")}>
          <select value={map.engine} onChange={(e) => onChange({ ...map, engine: e.target.value as SlotMap["engine"] })}>
            <option>xelatex</option><option>lualatex</option><option>pdflatex</option>
          </select>
        </Field>
      </div>
      <div>
        <div className="field-label">{t("template.identityCommands")}</div>
        <small className="field-hint">{t("template.identityHint")}</small>
        {commands.map(([cmd, key]) => (
          <div className="kv-row" key={cmd}>
            <code>\{cmd}</code>
            <select value={key} onChange={(e) => setIdentity({ commands: { ...map.identity.commands, [cmd]: e.target.value } })}>
              {IDENTITY_KEYS.concat(IDENTITY_KEYS.includes(key) ? [] : [key]).map((k) => <option key={k}>{k}</option>)}
            </select>
            <button className="icon-button" onClick={() => { const commands = { ...map.identity.commands }; delete commands[cmd]; setIdentity({ commands }); }}><Trash size={16} /></button>
          </div>
        ))}
        <div className="kv-row">
          <input placeholder="namapeserta" value={newCmd} onChange={(e) => setNewCmd(e.target.value.replace(/[^a-zA-Z]/g, ""))} />
          <span />
          <Button small icon={<Plus size={14} />} disabled={!newCmd || newCmd in map.identity.commands}
            onClick={() => { setIdentity({ commands: { ...map.identity.commands, [newCmd]: "name" } }); setNewCmd(""); }}>{t("common.add")}</Button>
        </div>
      </div>
      <div className="form-grid">
        <Field label={t("template.identityInputs")} hint="data/identitas, data/kelas">
          <input value={map.identity.inputs.join(", ")} onChange={(e) => setIdentity({ inputs: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
        </Field>
        <Field label={t("template.marker")}>
          <input value={map.identity.marker ?? ""} onChange={(e) => setIdentity({ marker: e.target.value })} />
        </Field>
      </div>
      <div>
        <div className="field-label">{t("template.sectionSlots")}</div>
        <small className="field-hint">{t("template.documentationRequired")}</small>
        {slots.map(([key, slot]) => (
          <div className="slot-row" key={key}>
            <code>{key}</code>
            <select value={slot.file} onChange={(e) => onChange({ ...map, slots: { ...map.slots, [key]: { ...slot, file: e.target.value } } })}>
              {files.concat(files.includes(slot.file) ? [] : [slot.file]).map((f) => <option key={f}>{f}</option>)}
            </select>
            <input placeholder={t("template.slotHeading")} value={slot.heading ?? ""} onChange={(e) => onChange({ ...map, slots: { ...map.slots, [key]: { ...slot, heading: e.target.value } } })} />
            <button className="icon-button" disabled={key === "documentation"} onClick={() => { const slots = { ...map.slots }; delete slots[key]; onChange({ ...map, slots }); }}><Trash size={16} /></button>
          </div>
        ))}
        <div className="slot-row">
          <select value={newSlot} onChange={(e) => setNewSlot(e.target.value)}>
            {SLOT_KEYS.filter((k) => !(k in map.slots)).map((k) => <option key={k}>{k}</option>)}
          </select>
          <span /><span />
          <Button small icon={<Plus size={14} />} disabled={!newSlot || newSlot in map.slots}
            onClick={() => onChange({ ...map, slots: { ...map.slots, [newSlot]: { file: files[0] ?? "", heading: "" } } })}>{t("common.add")}</Button>
        </div>
      </div>
    </div>
  );
}

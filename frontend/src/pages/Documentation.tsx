import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DndContext, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy, rectSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { CheckCircle, DotsSixVertical, Plus, Sparkle, Trash, X } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { Evidence, Fact, Step, StepResult } from "../api/types";
import { useAI } from "../ai/useAI";
import { useAutosave, useProjectCtx } from "../hooks";
import { Button, Dropzone, Empty, ErrorText, Field, SaveIndicator, Tag, notify } from "../components/ui";

export default function Documentation() {
  const { t } = useTranslation();
  const { project, refresh } = useProjectCtx();
  const [selected, setSelected] = useState<string | null>(project.steps[0]?.id ?? null);
  const ai = useAI(project);
  const unplaced = project.evidence.filter((e) => e.step_id === null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  useEffect(() => {
    if (selected && !project.steps.some((s) => s.id === selected)) setSelected(project.steps[0]?.id ?? null);
  }, [project.steps, selected]);

  const addStep = async () => {
    const step = await api.createStep(project.id, { title: t("docs.newStepTitle") });
    await refresh();
    setSelected(step.id);
  };
  const onDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const ids = project.steps.map((s) => s.id);
    const next = arrayMove(ids, ids.indexOf(String(active.id)), ids.indexOf(String(over.id)));
    await api.reorderSteps(project.id, next);
    await refresh();
  };
  const upload = async (files: File[], stepId: string | null) => {
    const images = files.filter((f) => /^image\/(png|jpeg|webp)$/.test(f.type));
    if (!images.length) return;
    notify(t("docs.uploading", { count: images.length }));
    try {
      const result = await api.uploadEvidence(project.id, images, stepId);
      if (result.skipped.length) notify(t("docs.skipped", { count: result.skipped.length }), "bad");
      await refresh();
    } catch (e) {
      notify((e as Error).message, "bad");
    }
  };
  const matchAll = async () => {
    const result = await ai.run({ operation: "match_evidence" });
    if (result) await refresh();
  };
  const step = project.steps.find((s) => s.id === selected) ?? null;

  return (
    <div className="page wide">
      <div className="page-heading">
        <div><div className="eyebrow">{project.title}</div><h1>{t("docs.title")}</h1><p>{t("docs.subtitle")}</p></div>
        <div className="button-row">
          {unplaced.length > 0 && ai.profile && (
            <Button icon={<Sparkle size={16} />} busy={ai.busy === "match_evidence"} onClick={matchAll}>{t("docs.aiMatch")}</Button>
          )}
          <Button variant="primary" icon={<Plus size={16} weight="bold" />} onClick={addStep}>{t("docs.addStep")}</Button>
        </div>
      </div>
      {ai.error && ai.error !== "no_profile" && <ErrorText error={new Error(ai.error)} />}
      {ai.error === "no_profile" && <div className="note">{t("docs.aiNeedProfile")}</div>}
      <div className="docs-layout">
        <div className="card">
          <div className="card-title"><h3>{t("docs.steps")}</h3><span className="field-hint">{project.steps.length}</span></div>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={project.steps.map((s) => s.id)} strategy={verticalListSortingStrategy}>
              <div className="step-list">
                {project.steps.map((s, i) => (
                  <StepItem key={s.id} step={s} index={i} count={project.evidence.filter((e) => e.step_id === s.id).length}
                    selected={s.id === selected} onSelect={() => setSelected(s.id)} />
                ))}
              </div>
            </SortableContext>
          </DndContext>
          <Dropzone onFiles={(files) => upload(files, null)} accept="image/png,image/jpeg,image/webp" compact>{t("docs.dropImages")}</Dropzone>
          {unplaced.length > 0 && <UnplacedPanel items={unplaced} steps={project.steps} onChanged={refresh} />}
        </div>
        {step ? (
          <StepEditor key={step.id} step={step} evidence={project.evidence.filter((e) => e.step_id === step.id)} steps={project.steps}
            onUpload={(files) => upload(files, step.id)} ai={ai} onChanged={refresh} onDeleted={() => setSelected(null)} />
        ) : (
          <Empty title={t("docs.selectStep")} action={<Button onClick={addStep}>{t("docs.addStep")}</Button>} />
        )}
      </div>
    </div>
  );
}

function StepItem({ step, index, count, selected, onSelect }: { step: Step; index: number; count: number; selected: boolean; onSelect: () => void }) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: step.id });
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`step-item ${selected ? "selected" : ""} ${isDragging ? "dragging" : ""}`} onClick={onSelect}>
      <span className="handle" {...attributes} {...listeners}><DotsSixVertical size={16} /></span>
      <div className="body">
        <strong>{index + 1}. {step.title}</strong>
        <small>{t("docs.images", { count })}{step.not_applicable ? " · N/A" : ""}</small>
      </div>
      <span className={`dot ${step.reviewed ? "good" : ""}`} title={step.reviewed ? t("docs.reviewed") : t("docs.draft")} />
    </div>
  );
}

function UnplacedPanel({ items, steps, onChanged }: { items: Evidence[]; steps: Step[]; onChanged: () => Promise<unknown> }) {
  const { t } = useTranslation();
  const proposals = items.filter((e) => e.match?.step_id);
  const applyAll = async () => {
    for (const e of proposals) await api.patchEvidence(e.id, { step_id: e.match.step_id! });
    await onChanged();
    notify(t("docs.aiApplied"), "good");
  };
  return (
    <div>
      <div className="card-title"><h3>{t("docs.unassigned")} · {items.length}</h3>
        {proposals.length > 0 && <Button small variant="primary" onClick={applyAll}>{t("docs.applyMatches")}</Button>}</div>
      {proposals.length > 0 && <p className="field-hint">{t("docs.matchHint", { count: proposals.length })}</p>}
      {items.map((e) => (
        <div className="match-row" key={e.id}>
          <img src={e.url} alt="" />
          <div>
            <div>{e.name}</div>
            {e.match?.step_id && <small className="field-hint">→ {steps.find((s) => s.id === e.match.step_id)?.title} · {t("docs.confidence", { pct: Math.round((e.match.confidence ?? 0) * 100) })}</small>}
          </div>
          <select value={e.match?.step_id ?? ""} onChange={async (ev) => { if (ev.target.value) { await api.patchEvidence(e.id, { step_id: ev.target.value }); await onChanged(); } }}>
            <option value="">{t("docs.moveTo")}</option>
            {steps.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
          </select>
        </div>
      ))}
    </div>
  );
}

interface EditorProps {
  step: Step; evidence: Evidence[]; steps: Step[]; ai: ReturnType<typeof useAI>;
  onUpload: (files: File[]) => void; onChanged: () => Promise<unknown>; onDeleted: () => void;
}

function StepEditor({ step, evidence, steps, ai, onUpload, onChanged, onDeleted }: EditorProps) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [form, setForm] = useState({ title: step.title, instruction: step.instruction, notes: step.notes, narrative: step.narrative, result: step.result, not_applicable: step.not_applicable });
  const [facts, setFacts] = useState<Fact[]>(step.facts);
  const [showDrafts, setShowDrafts] = useState(false);
  const drafts = useQuery({ queryKey: ["drafts", step.id], queryFn: () => api.drafts(step.project_id, step.id), enabled: showDrafts });
  useEffect(() => { setFacts(step.facts); }, [step.facts]);
  useEffect(() => {
    // Server-side changes (AI applied, review) refresh the form only when the user has nothing pending.
    setForm((f) => (JSON.stringify(f) === JSON.stringify({ title: step.title, instruction: step.instruction, notes: step.notes, narrative: step.narrative, result: step.result, not_applicable: step.not_applicable }) ? f
      : { ...f, narrative: f.narrative || step.narrative }));
  }, [step.narrative]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = useAutosave({ ...form, facts }, async (value) => {
    await api.patchStep(step.id, value);
    await onChanged();
  });
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const sorted = useMemo(() => [...evidence].sort((a, b) => a.position - b.position), [evidence]);

  const runAI = async (operation: "analyze_evidence" | "describe_step") => {
    await save.flush();
    const result = await ai.run({ operation, step_id: step.id });
    if (!result) return;
    notify(result.applied ? t("docs.aiApplied") : t("docs.aiKeptYours"), result.applied ? "good" : "muted");
    await onChanged();
    void client.invalidateQueries({ queryKey: ["drafts", step.id] });
    if (!result.applied) setShowDrafts(true);
  };
  const review = async (reviewed: boolean) => {
    await save.flush();
    try {
      await api.reviewStep(step.id, reviewed, step.revision);
      await onChanged();
    } catch (e) {
      notify((e as Error).message, "bad");
      await onChanged();
    }
  };
  const remove = async () => {
    if (!window.confirm(t("common.confirmDelete", { what: step.title }))) return;
    await api.deleteStep(step.id);
    onDeleted();
    await onChanged();
  };
  const onEvidenceDrag = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const ids = sorted.map((e) => e.id);
    await api.reorderEvidence(step.id, arrayMove(ids, ids.indexOf(String(active.id)), ids.indexOf(String(over.id))));
    await onChanged();
  };
  const applyDraft = async (id: string, field: "narrative" | "facts") => {
    await api.applyDraft(id, field);
    await onChanged();
    const fresh = await api.steps(step.project_id);
    const me = fresh.find((s) => s.id === step.id);
    if (me) {
      setForm((f) => ({ ...f, narrative: me.narrative }));
      setFacts(me.facts);
    }
    void client.invalidateQueries({ queryKey: ["drafts", step.id] });
  };

  return (
    <div className="card">
      <div className="card-title">
        <div className="button-row">
          {step.reviewed ? <Tag tone="good"><CheckCircle size={12} weight="fill" />{t("docs.reviewed")}</Tag> : <Tag tone="warn">{t("docs.draft")}</Tag>}
          <SaveIndicator state={save.state} error={save.error} />
        </div>
        <div className="button-row">
          {step.reviewed ? <Button small onClick={() => review(false)}>{t("docs.unreview")}</Button>
            : <Button small variant="primary" icon={<CheckCircle size={14} />} onClick={() => review(true)}>{t("docs.review")}</Button>}
          <Button small variant="danger" icon={<Trash size={14} />} onClick={remove}>{t("docs.deleteStep")}</Button>
        </div>
      </div>
      <div className="form-grid">
        <Field label={t("docs.stepTitle")}><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
        <Field label={t("docs.result")}>
          <select value={form.result} onChange={(e) => setForm({ ...form, result: e.target.value as StepResult })}>
            {(["unknown", "success", "failed", "partial"] as StepResult[]).map((r) => <option key={r} value={r}>{t(`docs.results.${r}`)}</option>)}
          </select>
        </Field>
      </div>
      <Field label={t("docs.instruction")}><textarea value={form.instruction} onChange={(e) => setForm({ ...form, instruction: e.target.value })} /></Field>

      <div className="card-title">
        <h3>{t("docs.images", { count: sorted.length })}</h3>
        {ai.profile && sorted.length > 0 && (
          <Button small icon={<Sparkle size={14} />} busy={ai.busy === "analyze_evidence"} onClick={() => runAI("analyze_evidence")}>{t("docs.aiAnalyze")}</Button>
        )}
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onEvidenceDrag}>
        <SortableContext items={sorted.map((e) => e.id)} strategy={rectSortingStrategy}>
          <div className="thumb-grid">
            {sorted.map((e) => <Thumb key={e.id} item={e} steps={steps} onChanged={onChanged} />)}
          </div>
        </SortableContext>
      </DndContext>
      <Dropzone onFiles={onUpload} accept="image/png,image/jpeg,image/webp" compact>{t("docs.dropImages")}</Dropzone>

      <div>
        <div className="field-label">{t("docs.facts")}</div>
        {facts.length === 0 ? <p className="field-hint">{t("docs.noFacts")}</p> : (
          <div className="fact-list">
            {facts.map((f, i) => (
              <div className="fact" key={i}>
                <span className="type">{f.type}</span>
                <input value={f.value} onChange={(e) => setFacts(facts.map((x, j) => (j === i ? { ...x, value: e.target.value, reviewed: false } : x)))} />
                <div className="button-row">
                  <label className="field inline" style={{ fontSize: 11 }}><input type="checkbox" checked={f.reviewed} onChange={(e) => setFacts(facts.map((x, j) => (j === i ? { ...x, reviewed: e.target.checked } : x)))} />{t("docs.factReviewed")}</label>
                  <button className="icon-button" onClick={() => setFacts(facts.filter((_, j) => j !== i))}><X size={14} /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Field label={t("docs.notes")}><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field>
      <div className="card-title">
        <div className="field-label">{t("docs.narrative")}</div>
        <div className="button-row">
          {ai.profile && <Button small icon={<Sparkle size={14} />} busy={ai.busy === "describe_step"} onClick={() => runAI("describe_step")}>{t("docs.aiDescribe")}</Button>}
          <Button small variant="ghost" onClick={() => setShowDrafts((v) => !v)}>{t("docs.drafts")}</Button>
        </div>
      </div>
      <textarea className="tall" value={form.narrative} onChange={(e) => setForm({ ...form, narrative: e.target.value })} />
      {showDrafts && (
        <div className="draft-list">
          {drafts.data?.length === 0 && <p className="field-hint">{t("docs.noDrafts")}</p>}
          {drafts.data?.map((d) => (
            <div className="draft" key={d.id}>
              <div className="card-title"><span className="field-hint">{d.operation} · {new Date(d.created_at).toLocaleString()}{d.applied ? " · ✓" : ""}</span>
                {"narrative" in d.content && <Button small onClick={() => applyDraft(d.id, "narrative")}>{t("docs.applyDraft")}</Button>}
                {"facts" in d.content && !("narrative" in d.content && (d.content.narrative as string)) && <Button small onClick={() => applyDraft(d.id, "facts")}>{t("docs.applyDraft")}</Button>}
              </div>
              <pre>{String(d.content.narrative ?? (d.content.facts as Fact[] | undefined)?.map((f) => `• ${f.type}: ${f.value}`).join("\n") ?? JSON.stringify(d.content))}</pre>
            </div>
          ))}
        </div>
      )}
      <Field label={t("docs.notApplicable")} hint={t("common.optional")}><input value={form.not_applicable} onChange={(e) => setForm({ ...form, not_applicable: e.target.value })} /></Field>
    </div>
  );
}

function Thumb({ item, steps, onChanged }: { item: Evidence; steps: Step[]; onChanged: () => Promise<unknown> }) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id });
  const [caption, setCaption] = useState(item.caption);
  useAutosave(caption, async (value) => { await api.patchEvidence(item.id, { caption: value }); });
  const remove = async () => {
    if (!window.confirm(t("common.confirmDelete", { what: item.name }))) return;
    await api.deleteEvidence(item.id);
    await onChanged();
  };
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} className={`thumb ${isDragging ? "dragging" : ""}`}>
      <a href={item.url} target="_blank" rel="noreferrer"><img src={item.url} alt={item.name} loading="lazy" /></a>
      <div className="thumb-bar">
        <span className="handle" {...attributes} {...listeners}><DotsSixVertical size={14} /></span>
        <span title={item.name}>{item.name}</span>
        <select value="" title={t("docs.moveTo")} onChange={async (e) => { if (e.target.value) { await api.patchEvidence(item.id, { step_id: e.target.value }); await onChanged(); } }} style={{ width: 28, padding: 2 }}>
          <option value="">→</option>
          {steps.filter((s) => s.id !== item.step_id).map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
        </select>
        <button className="icon-button" onClick={remove}><X size={13} /></button>
      </div>
      <input placeholder={t("docs.caption")} value={caption} onChange={(e) => setCaption(e.target.value)} />
    </div>
  );
}

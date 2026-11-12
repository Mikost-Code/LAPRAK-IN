import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { CheckCircle, Sparkle, Warning } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { Section } from "../api/types";
import { useAI } from "../ai/useAI";
import { useAutosave, useProjectCtx } from "../hooks";
import { Button, ErrorText, SaveIndicator, Tag, notify } from "../components/ui";

export default function Review() {
  const { t } = useTranslation();
  const { project, refresh } = useProjectCtx();
  const navigate = useNavigate();
  const ai = useAI(project);
  const blockers = useQuery({ queryKey: ["blockers", project.id], queryFn: () => api.blockers(project.id) });
  const go = (target: string) => {
    const route = { template: "template", steps: "docs", step: "docs", evidence: "docs", section: "review", sections: "review" }[target] ?? "setup";
    navigate(`/projects/${project.id}/${route}`);
  };
  const approveAll = async () => {
    for (const s of project.sections) if (!s.reviewed) await api.patchSection(project.id, s.id, { reviewed: true, revision: s.revision });
    await api.patchProject(project.id, { sections_reviewed: true });
    await refresh();
    await blockers.refetch();
  };
  return (
    <div className="page">
      <div className="page-heading">
        <div><div className="eyebrow">{project.title}</div><h1>{t("review.title")}</h1><p>{t("review.subtitle")}</p></div>
        {project.sections_reviewed ? <Tag tone="good"><CheckCircle size={12} weight="fill" />{t("review.approved")}</Tag>
          : <Button variant="primary" onClick={approveAll} disabled={project.sections.some((s) => !s.content.trim())}>{t("review.approveAll")}</Button>}
      </div>
      <div className="card">
        <h2>{t("review.blockers")}</h2>
        {blockers.data?.length === 0 ? <Tag tone="good">{t("review.clean")}</Tag> : (
          <div className="blocker-list">
            {blockers.data?.map((b, i) => (
              <div className="blocker" key={i}><Warning size={16} /><span>{b.message}</span><Button small onClick={() => go(b.target)}>{t("review.fix")}</Button></div>
            ))}
          </div>
        )}
      </div>
      {ai.error && ai.error !== "no_profile" && <ErrorText error={new Error(ai.error)} />}
      <h2>{t("review.sections")}</h2>
      {project.sections.map((s) => <SectionEditor key={s.id} section={s} ai={ai} onChanged={async () => { await refresh(); await blockers.refetch(); }} />)}
    </div>
  );
}

function SectionEditor({ section, ai, onChanged }: { section: Section; ai: ReturnType<typeof useAI>; onChanged: () => Promise<unknown> }) {
  const { t } = useTranslation();
  const { project } = useProjectCtx();
  const [content, setContent] = useState(section.content);
  useEffect(() => { setContent((c) => (c.trim() ? c : section.content)); }, [section.content]);
  const save = useAutosave(content, async (value) => {
    await api.patchSection(project.id, section.id, { content: value });
    await onChanged();
  });
  const draft = async () => {
    await save.flush();
    const result = await ai.run({ operation: "draft_section", section_id: section.id }, "draft:" + section.id);
    if (!result) return;
    if (result.applied) {
      setContent(String(result.content.content ?? ""));
      notify(t("docs.aiApplied"), "good");
    } else {
      notify(t("docs.aiKeptYours"));
      if (window.confirm(String(result.content.content ?? "").slice(0, 600) + "\n\n" + t("docs.applyDraft") + "?")) {
        await api.applyDraft(result.draft.id, "content");
        setContent(String(result.content.content ?? ""));
      }
    }
    await onChanged();
  };
  const toggle = async () => {
    await save.flush();
    try {
      await api.patchSection(project.id, section.id, { reviewed: !section.reviewed, revision: section.revision });
      await onChanged();
    } catch (e) {
      notify((e as Error).message, "bad");
    }
  };
  return (
    <div className="card">
      <div className="card-title">
        <div className="button-row"><h3>{section.title}</h3>{section.reviewed ? <Tag tone="good">{t("review.sectionReviewed")}</Tag> : <Tag tone="warn">{t("docs.draft")}</Tag>}<SaveIndicator state={save.state} error={save.error} /></div>
        <div className="button-row">
          {ai.profile && <Button small icon={<Sparkle size={14} />} busy={ai.busy === "draft:" + section.id} onClick={draft}>{t("review.aiDraft")}</Button>}
          <Button small variant={section.reviewed ? undefined : "primary"} onClick={toggle} disabled={!content.trim()}>{section.reviewed ? t("docs.unreview") : t("docs.review")}</Button>
        </div>
      </div>
      <textarea className="tall" value={content} onChange={(e) => setContent(e.target.value)} />
    </div>
  );
}

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowSquareOut, FilePdf } from "@phosphor-icons/react";
import { api } from "../api/client";
import { useProjectCtx } from "../hooks";
import { Button, Empty, ErrorText, Tag } from "../components/ui";

export default function Export() {
  const { t } = useTranslation();
  const { project } = useProjectCtx();
  const [error, setError] = useState<unknown>(null);
  const builds = useQuery({
    queryKey: ["builds", project.id], queryFn: () => api.builds(project.id),
    refetchInterval: (query) => (query.state.data?.some((b) => b.status === "queued" || b.status === "running") ? 2000 : false),
  });
  const latex = useQuery({ queryKey: ["latex"], queryFn: api.latexStatus, staleTime: 60000 });
  const blockers = useQuery({ queryKey: ["blockers", project.id], queryFn: () => api.blockers(project.id) });
  const start = async (final: boolean) => {
    setError(null);
    try {
      await api.startBuild(project.id, final);
      await builds.refetch();
    } catch (e) {
      setError(e);
    }
  };
  const running = builds.data?.some((b) => b.status === "queued" || b.status === "running");
  const latest = builds.data?.find((b) => b.status === "done");
  const ready = Boolean(project.template && ["mapped", "verified"].includes(project.template.status));
  return (
    <div className="page">
      <div className="page-heading">
        <div><div className="eyebrow">{project.title}</div><h1>{t("pdf.title")}</h1><p>{t("pdf.subtitle")}</p></div>
        <div className="button-row">
          <Button icon={<FilePdf size={16} />} busy={running} disabled={!ready || !latex.data?.available} onClick={() => start(false)}>{t("pdf.build")}</Button>
          <Button variant="primary" icon={<FilePdf size={16} weight="fill" />} busy={running} disabled={!ready || !latex.data?.available || (blockers.data?.length ?? 1) > 0} onClick={() => start(true)}>{t("pdf.buildFinal")}</Button>
        </div>
      </div>
      {latex.data && (latex.data.available ? <Tag tone="good">{t("pdf.compilerOk", { version: latex.data.version })}</Tag> : <ErrorText error={new Error(t("pdf.compilerMissing") + (latex.data.error ? "\n" + latex.data.error : ""))} />)}
      <ErrorText error={error} />
      {latest?.pdf_url && (
        <div className="card">
          <div className="card-title">
            <div className="button-row"><h3>{latest.final ? "Final" : "Preview"} · rev {latest.revision}</h3>{latest.stale ? <Tag tone="warn">{t("pdf.stale")}</Tag> : <Tag tone="good">{t("pdf.latest")}</Tag>}</div>
            <a className="button" href={latest.pdf_url} target="_blank" rel="noreferrer"><ArrowSquareOut size={16} />{t("pdf.download")}</a>
          </div>
          <iframe className="pdf-frame" src={latest.pdf_url} title="PDF" />
        </div>
      )}
      <div className="card">
        <h3>{t("pdf.title")} · {builds.data?.length ?? 0}</h3>
        {builds.data?.length === 0 && <Empty title={t("pdf.noBuilds")} />}
        {builds.data?.map((b) => (
          <div className="build-row" key={b.id}>
            <Tag tone={b.status === "done" ? "good" : b.status === "failed" ? "bad" : "warn"}>{b.status}</Tag>
            <span>{new Date(b.created_at).toLocaleString()} · rev {b.revision}{b.final ? " · final" : ""}</span>
            {b.pdf_url ? <a className="button small" href={b.pdf_url} target="_blank" rel="noreferrer">{t("pdf.download")}</a> : <span />}
            {b.status === "failed" && <pre>{b.error}</pre>}
          </div>
        ))}
      </div>
    </div>
  );
}

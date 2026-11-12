import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { Brain, FilePdf, FileText, House, Images, ListChecks, SignOut, SlidersHorizontal } from "@phosphor-icons/react";
import { api } from "./api/client";
import type { Lang } from "./api/types";
import { setLocale } from "./i18n";
import { useMe, useProject } from "./hooks";
import { ErrorText, Spinner, Toasts } from "./components/ui";
import Login from "./pages/Login";
import Home from "./pages/Home";
import Setup from "./pages/Setup";
import TemplatePage from "./pages/TemplatePage";
import Documentation from "./pages/Documentation";
import Review from "./pages/Review";
import Export from "./pages/Export";
import AISettings from "./pages/AISettings";

export default function App() {
  const me = useMe();
  useEffect(() => {
    if (me.data?.locale) setLocale(me.data.locale);
  }, [me.data?.locale]);
  if (me.isLoading) return <div className="login"><Spinner /></div>;
  if (!me.data) {
    return (
      <>
        <Routes>
          <Route path="/login" element={<Login onLogin={() => me.refetch()} />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
        <Toasts />
      </>
    );
  }
  return (
    <>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Home />} />
          <Route path="ai" element={<AISettings />} />
          <Route path="projects/:id" element={<ProjectLayout />}>
            <Route index element={<Navigate to="setup" replace />} />
            <Route path="setup" element={<Setup />} />
            <Route path="template" element={<TemplatePage />} />
            <Route path="docs" element={<Documentation />} />
            <Route path="review" element={<Review />} />
            <Route path="pdf" element={<Export />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      <Toasts />
    </>
  );
}

function Shell() {
  const { t, i18n } = useTranslation();
  const me = useMe();
  const client = useQueryClient();
  const navigate = useNavigate();
  const { id } = useParams();
  const blockers = useQuery({ queryKey: ["blockers", id], queryFn: () => api.blockers(id!), enabled: Boolean(id), refetchInterval: 15000 });
  const project = useProject(id);
  const changeLocale = async (locale: Lang) => {
    setLocale(locale);
    await api.setLocale(locale).catch(() => undefined);
  };
  const logout = async () => {
    await api.logout();
    client.clear();
    navigate("/login");
  };
  const initials = (me.data?.name || me.data?.email || "?").slice(0, 1).toUpperCase();
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand">
          <div className="brand-mark">L</div>
          <div><strong>{t("app.name")}</strong><small>{t("app.tagline")}</small></div>
        </div>
        <nav>
          <NavLink to="/" end className="nav-item"><House size={18} />{t("nav.home")}</NavLink>
          <NavLink to="/ai" className="nav-item"><Brain size={18} />{t("nav.ai")}</NavLink>
        </nav>
        {id && project.data && (
          <div>
            <div className="sidebar-label">{project.data.title}</div>
            <nav>
              <NavLink to={`/projects/${id}/setup`} className="nav-item"><SlidersHorizontal size={18} />{t("nav.setup")}</NavLink>
              <NavLink to={`/projects/${id}/template`} className="nav-item"><FileText size={18} />{t("nav.template")}
                {project.data.template ? null : <span className="count warn">!</span>}</NavLink>
              <NavLink to={`/projects/${id}/docs`} className="nav-item"><Images size={18} />{t("nav.docs")}<span className="count">{project.data.steps.length}</span></NavLink>
              <NavLink to={`/projects/${id}/review`} className="nav-item"><ListChecks size={18} />{t("nav.review")}
                {blockers.data?.length ? <span className="count warn">{blockers.data.length}</span> : null}</NavLink>
              <NavLink to={`/projects/${id}/pdf`} className="nav-item"><FilePdf size={18} />{t("nav.pdf")}</NavLink>
            </nav>
          </div>
        )}
        <div className="sidebar-bottom">
          <div className="locale-toggle">
            {(["id", "en"] as Lang[]).map((l) => (
              <button key={l} className={i18n.language === l ? "active" : ""} onClick={() => changeLocale(l)}>{l.toUpperCase()}</button>
            ))}
          </div>
          <div className="user-row">
            {me.data?.picture ? <img className="avatar" src={me.data.picture} alt="" referrerPolicy="no-referrer" /> : <div className="avatar">{initials}</div>}
            <div><strong>{me.data?.name || me.data?.email}</strong><small>{me.data?.email}</small></div>
            <button className="icon-button" onClick={logout} title={t("nav.logout")}><SignOut size={18} /></button>
          </div>
        </div>
      </aside>
      <div className="app-main">
        <Outlet />
      </div>
    </div>
  );
}

function ProjectLayout() {
  const { id } = useParams();
  const project = useProject(id);
  const client = useQueryClient();
  if (project.isLoading) return <div className="page"><Spinner /></div>;
  if (project.error || !project.data) return <div className="page"><ErrorText error={project.error ?? new Error("Proyek tidak ditemukan.")} /></div>;
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["project", id] }),
    client.invalidateQueries({ queryKey: ["blockers", id] }),
  ]);
  return <Outlet context={{ project: project.data, refresh }} />;
}

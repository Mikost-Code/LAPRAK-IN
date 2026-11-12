import type {
  AIProfile, Blocker, Build, CompleteResult, Draft, Evidence, Lang, Me, ProjectRow, PromptPackage, Section, SlotMap,
  Snapshot, Step, Template,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown, raw?: FormData): Promise<T> {
  const headers: Record<string, string> = { "x-laprak-client": "1" };
  if (body !== undefined) headers["content-type"] = "application/json";
  const response = await fetch("/api" + path, {
    method,
    headers,
    credentials: "include",
    body: raw ?? (body === undefined ? undefined : JSON.stringify(body)),
  });
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  let data: unknown = text;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    /* non-JSON error body */
  }
  if (!response.ok) {
    const detail = (data as { detail?: unknown })?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg ?? JSON.stringify(d)).join("; ") : response.statusText;
    throw new ApiError(response.status, message);
  }
  return data as T;
}

const get = <T,>(p: string) => request<T>("GET", p);
const post = <T,>(p: string, b?: unknown) => request<T>("POST", p, b);
const patch = <T,>(p: string, b?: unknown) => request<T>("PATCH", p, b);
const put = <T,>(p: string, b?: unknown) => request<T>("PUT", p, b);
const del = (p: string) => request<void>("DELETE", p);

export const api = {
  health: () => get<{ ok: boolean; dev_login: boolean; google: boolean }>("/health"),
  me: () => get<Me>("/auth/me"),
  devLogin: (email: string, name: string) => post<Me>("/auth/dev-login", { email, name }),
  logout: () => post("/auth/logout"),
  setLocale: (locale: Lang) => put<Me>("/auth/me/locale", { locale }),

  projects: () => get<ProjectRow[]>("/projects"),
  createProject: (body: { title: string; language: Lang; identity: Record<string, string> }) => post<ProjectRow>("/projects", body),
  project: (id: string) => get<Snapshot>(`/projects/${id}`),
  patchProject: (id: string, body: Partial<Pick<ProjectRow, "title" | "language" | "identity" | "ai_profile_id" | "sections_reviewed">>) =>
    patch<Snapshot>(`/projects/${id}`, body),
  deleteProject: (id: string) => del(`/projects/${id}`),
  blockers: (id: string) => get<Blocker[]>(`/projects/${id}/blockers`),

  sections: (id: string) => get<Section[]>(`/projects/${id}/sections`),
  patchSection: (pid: string, sid: string, body: Partial<Pick<Section, "title" | "content" | "reviewed" | "revision">>) =>
    patch<Section>(`/projects/${pid}/sections/${sid}`, body),

  steps: (pid: string) => get<Step[]>(`/projects/${pid}/steps`),
  createStep: (pid: string, body: { title: string; instruction?: string; position?: number }) => post<Step>(`/projects/${pid}/steps`, body),
  patchStep: (id: string, body: Partial<Pick<Step, "title" | "instruction" | "notes" | "narrative" | "facts" | "result" | "not_applicable">>) =>
    patch<Step>(`/steps/${id}`, body),
  reviewStep: (id: string, reviewed: boolean, revision?: number) => post<Step>(`/steps/${id}/review`, { reviewed, revision }),
  reorderSteps: (pid: string, ids: string[]) => put<Step[]>(`/projects/${pid}/steps/order`, { ids }),
  deleteStep: (id: string) => del(`/steps/${id}`),

  evidence: (pid: string) => get<Evidence[]>(`/projects/${pid}/evidence`),
  uploadEvidence: (pid: string, files: File[], stepId?: string | null) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f, f.name));
    if (stepId) form.append("step_id", stepId);
    return request<{ created: Evidence[]; skipped: { name: string; reason: string }[] }>("POST", `/projects/${pid}/evidence`, undefined, form);
  },
  patchEvidence: (id: string, body: { step_id?: string | null; position?: number; caption?: string; match?: Evidence["match"] }) =>
    patch<Evidence>(`/evidence/${id}`, body),
  reorderEvidence: (stepId: string, ids: string[]) => put<Evidence[]>(`/steps/${stepId}/evidence/order`, { ids }),
  deleteEvidence: (id: string) => del(`/evidence/${id}`),

  template: (pid: string) => get<Template | null>(`/projects/${pid}/template`),
  uploadTemplate: (pid: string, file: File) => {
    const form = new FormData();
    form.append("file", file, file.name);
    return request<Template>("POST", `/projects/${pid}/template`, undefined, form);
  },
  setSlots: (pid: string, slot_map: SlotMap) => put<Template>(`/projects/${pid}/template/slots`, { slot_map }),
  templateFile: (pid: string, path: string) => get<{ path: string; content: string }>(`/projects/${pid}/template/file?path=${encodeURIComponent(path)}`),
  deleteTemplate: (pid: string) => del(`/projects/${pid}/template`),

  profiles: () => get<AIProfile[]>("/ai-profiles"),
  createProfile: (body: Partial<AIProfile> & { api_key?: string }) => post<AIProfile>("/ai-profiles", body),
  patchProfile: (id: string, body: Partial<AIProfile> & { api_key?: string }) => patch<AIProfile>(`/ai-profiles/${id}`, body),
  deleteProfile: (id: string) => del(`/ai-profiles/${id}`),
  profileSecret: (id: string) => get<{ api_key: string }>(`/ai-profiles/${id}/secret`),
  recordTest: (id: string, text_ok: boolean, vision_ok: boolean) => post<AIProfile>(`/ai-profiles/${id}/test-result`, { text_ok, vision_ok }),

  prepare: (pid: string, body: { operation: string; step_id?: string; section_id?: string; evidence_ids?: string[]; text?: string }) =>
    post<PromptPackage>(`/projects/${pid}/ai/prepare`, body),
  complete: (pid: string, body: { operation: string; raw: string; target: Record<string, unknown>; cache_key?: string }) =>
    post<CompleteResult>(`/projects/${pid}/ai/complete`, body),
  drafts: (pid: string, targetId?: string) => get<Draft[]>(`/projects/${pid}/drafts${targetId ? `?target_id=${targetId}` : ""}`),
  applyDraft: (id: string, field: "narrative" | "facts" | "content") => post(`/drafts/${id}/apply`, { field }),

  builds: (pid: string) => get<Build[]>(`/projects/${pid}/builds`),
  startBuild: (pid: string, final = false) => post<Build>(`/projects/${pid}/builds?final=${final}`),
  build: (pid: string, id: string) => get<Build>(`/projects/${pid}/builds/${id}`),
  latexStatus: () => get<{ available: boolean; compiler?: string; version?: string; error?: string }>("/system/latex"),
};

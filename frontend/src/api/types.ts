export type Lang = "id" | "en";

export interface Me {
  id: string;
  email: string;
  name: string;
  picture: string;
  locale: Lang;
}

export interface ProjectRow {
  id: string;
  title: string;
  language: Lang;
  identity: Record<string, string>;
  template_id: string | null;
  ai_profile_id: string | null;
  revision: number;
  sections_reviewed: boolean;
  created_at: string;
  updated_at: string;
}

export interface Fact {
  type: string;
  value: string;
  source: "visible" | "user_note" | "document";
  reviewed: boolean;
}

export type StepResult = "unknown" | "success" | "failed" | "partial";

export interface Step {
  id: string;
  project_id: string;
  position: number;
  title: string;
  instruction: string;
  notes: string;
  narrative: string;
  facts: Fact[];
  result: StepResult;
  not_applicable: string;
  source_ref: Record<string, unknown>;
  reviewed: boolean;
  revision: number;
  updated_at: string;
}

export interface Evidence {
  id: string;
  project_id: string;
  step_id: string | null;
  position: number;
  path: string;
  name: string;
  hash: string;
  width: number;
  height: number;
  captured_at: string | null;
  caption: string;
  facts: Fact[];
  match: { step_id?: string | null; confidence?: number; reason?: string };
  url: string;
}

export interface Section {
  id: string;
  project_id: string;
  key: string;
  title: string;
  position: number;
  content: string;
  reviewed: boolean;
  revision: number;
}

export interface SlotMap {
  schema_version: number;
  name: string;
  main: string;
  engine: "xelatex" | "lualatex" | "pdflatex";
  identity: { commands: Record<string, string>; inputs: string[]; marker?: string };
  slots: Record<string, { file: string; heading?: string }>;
  required_assets?: string[];
}

export interface Template {
  id: string;
  project_id: string;
  kind: "latex" | "docx_converted";
  name: string;
  engine: string;
  root: string;
  main_path: string;
  slot_map: SlotMap;
  font_map: Record<string, string>;
  status: "uploaded" | "mapped" | "verified" | "failed";
  message: string;
  files: string[];
}

export interface Snapshot extends ProjectRow {
  template: Template | null;
  steps: Step[];
  evidence: Evidence[];
  sections: Section[];
}

export interface Blocker {
  message: string;
  target: string;
  id?: string;
}

export interface AIProfile {
  id: string;
  name: string;
  base_url: string;
  text_model: string;
  vision_model: string;
  structured_mode: "json_object" | "json_schema" | "prompt";
  has_api_key: boolean;
  text_ok: boolean;
  vision_ok: boolean;
  tested_at: string | null;
}

export interface PromptPart {
  type: "text" | "image";
  text?: string;
  evidence_id?: string;
  url?: string;
}

export interface PromptPackage {
  operation: string;
  language: Lang;
  system: string;
  messages: { role: string; content: PromptPart[] }[];
  schema_name: string;
  json_schema: Record<string, unknown>;
  needs_vision: boolean;
  cache_key: string;
  target: Record<string, unknown>;
}

export interface Draft {
  id: string;
  operation: string;
  target_kind: string;
  target_id: string;
  target_revision: number;
  content: Record<string, unknown>;
  applied: boolean;
  created_at: string;
}

export interface CompleteResult {
  draft: Draft;
  applied: boolean;
  content: Record<string, unknown>;
}

export interface Build {
  id: string;
  revision: number;
  status: "queued" | "running" | "done" | "failed";
  pdf_path: string;
  log: string;
  error: string;
  final: boolean;
  created_at: string;
  finished_at: string | null;
  pdf_url: string;
  stale: boolean;
}

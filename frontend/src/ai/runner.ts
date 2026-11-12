/**
 * Browser-side AI execution. The server never talks to a provider: it prepares a prompt package,
 * this module turns it into an OpenAI-compatible Chat Completions request against the user's own
 * endpoint (9Router on localhost, or any provider with base URL + key), then hands the raw JSON back
 * to the server for schema validation.
 */
import { api } from "../api/client";
import type { AIProfile, CompleteResult, PromptPackage } from "../api/types";

export class AIRunError extends Error {
  kind: "network" | "auth" | "quota" | "cors" | "format" | "cancelled" | "provider" | "config";
  retryable: boolean;
  constructor(kind: AIRunError["kind"], message: string, retryable = false) {
    super(message);
    this.kind = kind;
    this.retryable = retryable;
  }
}

async function imageToDataUrl(url: string, maxSide = 1600): Promise<string> {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw new AIRunError("network", "Gambar tidak dapat dimuat dari server.");
  const blob = await response.blob();
  const bitmap = await createImageBitmap(blob);
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const context = canvas.getContext("2d");
  if (!context) throw new AIRunError("format", "Canvas tidak tersedia.");
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return canvas.toDataURL("image/jpeg", 0.9);
}

export function classifyHttp(status: number, body: string): AIRunError {
  const low = body.slice(0, 65536).toLowerCase();
  if (low.includes("insufficient_quota") || low.includes("usage limit")) return new AIRunError("quota", "Kuota provider habis.");
  if (low.includes("invalid_api_key") || low.includes("invalid api key") || status === 401) return new AIRunError("auth", "API key ditolak provider (HTTP 401).");
  if (status === 403) return new AIRunError("provider", "Provider menolak akses (HTTP 403). Periksa izin model atau jaringan.");
  if (status === 404) return new AIRunError("config", "Endpoint atau model tidak ditemukan (HTTP 404). Periksa base URL dan nama model.");
  if (status === 429) return new AIRunError("quota", "Provider membatasi laju (HTTP 429). Coba lagi sebentar.", true);
  if (status >= 500) return new AIRunError("provider", `Provider bermasalah (HTTP ${status}).`, true);
  return new AIRunError("provider", `Provider memberi HTTP ${status}.`);
}

export interface RunOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  imageMaxSide?: number;
}

/** Calls the provider and returns the raw assistant text (expected to be JSON). */
export async function callProvider(profile: AIProfile, apiKey: string, pkg: PromptPackage, options: RunOptions = {}): Promise<string> {
  const model = pkg.needs_vision ? profile.vision_model || profile.text_model : profile.text_model;
  if (!model) throw new AIRunError("config", "Nama model belum diisi di profil AI.");
  if (pkg.needs_vision && !profile.vision_ok) throw new AIRunError("config", "Kemampuan gambar belum diuji untuk profil ini.");
  const messages: unknown[] = [{ role: "system", content: pkg.system }];
  for (const message of pkg.messages) {
    const parts: unknown[] = [];
    for (const part of message.content) {
      if (part.type === "text") parts.push({ type: "text", text: part.text });
      else if (part.url) parts.push({ type: "image_url", image_url: { url: await imageToDataUrl(part.url, options.imageMaxSide) } });
    }
    messages.push({ role: message.role, content: parts.length === 1 && message.content[0].type === "text" ? message.content[0].text : parts });
  }
  const payload: Record<string, unknown> = { model, messages, stream: false, temperature: 0.2 };
  if (profile.structured_mode === "json_schema") {
    payload.response_format = { type: "json_schema", json_schema: { name: pkg.schema_name, schema: pkg.json_schema } };
  } else if (profile.structured_mode === "json_object") {
    payload.response_format = { type: "json_object" };
  }
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), options.timeoutMs ?? 120000);
  options.signal?.addEventListener("abort", () => controller.abort(), { once: true });
  let response: Response;
  try {
    response = await fetch(profile.base_url.replace(/\/$/, "") + "/chat/completions", {
      method: "POST",
      headers: { "content-type": "application/json", ...(apiKey ? { authorization: `Bearer ${apiKey}` } : {}) },
      body: JSON.stringify(payload),
      signal: controller.signal,
      mode: "cors",
    });
  } catch (error) {
    window.clearTimeout(timer);
    if (options.signal?.aborted) throw new AIRunError("cancelled", "Dibatalkan.");
    if ((error as Error).name === "AbortError") throw new AIRunError("network", "Provider tidak menjawab sebelum batas waktu.", true);
    const local = /^https?:\/\/(localhost|127\.0\.0\.1)/.test(profile.base_url);
    throw new AIRunError(
      local ? "cors" : "network",
      local
        ? "Browser tidak dapat menghubungi 9Router/localhost. Pastikan 9Router berjalan, CORS untuk origin ini diizinkan, dan izin akses jaringan lokal di browser diberikan."
        : "Tidak dapat menghubungi endpoint AI. Periksa koneksi, base URL, dan kebijakan CORS provider.",
      true,
    );
  }
  window.clearTimeout(timer);
  const text = await response.text();
  if (!response.ok) throw classifyHttp(response.status, text);
  try {
    const data = JSON.parse(text);
    const content = data.choices?.[0]?.message?.content;
    if (typeof content === "string") return stripFences(content);
    if (Array.isArray(content)) return stripFences(content.map((c: { text?: string }) => c.text ?? "").join(""));
  } catch {
    /* fall through */
  }
  throw new AIRunError("format", "Respons provider bukan format Chat Completions yang dikenal.");
}

function stripFences(text: string): string {
  const match = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  return (match ? match[1] : text).trim();
}

/** Full round-trip: prepare on server -> provider in browser -> validate + store on server. */
export async function runOperation(
  projectId: string,
  profile: AIProfile,
  body: Parameters<typeof api.prepare>[1],
  options: RunOptions = {},
): Promise<CompleteResult> {
  const pkg = await api.prepare(projectId, body);
  const { api_key } = await api.profileSecret(profile.id);
  const raw = await callProvider(profile, api_key, pkg, options);
  return api.complete(projectId, { operation: pkg.operation, raw, target: pkg.target, cache_key: pkg.cache_key });
}

/** Probe text and (optionally) vision capability. Returns what worked; throws only on hard failures. */
export async function probeProfile(profile: AIProfile, apiKey: string, withVision: boolean): Promise<{ text: boolean; vision: boolean; error?: string }> {
  const nonce = "laprak-" + Math.random().toString(36).slice(2, 8);
  const schema = { type: "object", properties: { echo: { type: "string" }, image_text: { type: "string" } }, required: ["echo"] };
  const base: PromptPackage = {
    operation: "probe", language: "id", system: "Return only JSON matching the schema.", schema_name: "ConnectionProbe", json_schema: schema,
    needs_vision: false, cache_key: "", target: {},
    messages: [{ role: "user", content: [{ type: "text", text: `Reply with {"echo": "${nonce}"}. JSON schema: ${JSON.stringify(schema)}` }] }],
  };
  const textRaw = await callProvider(profile, apiKey, base);
  const text = safeParse(textRaw)?.echo === nonce;
  if (!withVision) return { text, vision: false };
  const canvas = document.createElement("canvas");
  canvas.width = 320;
  canvas.height = 120;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, 320, 120);
  ctx.fillStyle = "#000";
  ctx.font = "bold 48px sans-serif";
  const code = String(Math.floor(1000 + Math.random() * 9000));
  ctx.fillText(code, 70, 80);
  const probe: PromptPackage = {
    ...base, needs_vision: true,
    messages: [{ role: "user", content: [
      { type: "text", text: `Reply with {"echo": "${nonce}", "image_text": "<the digits in the image>"}. JSON schema: ${JSON.stringify(schema)}` },
      { type: "image", evidence_id: "probe", url: canvas.toDataURL("image/png") },
    ] }],
  };
  try {
    const raw = await callProvider({ ...profile, vision_ok: true }, apiKey, probe);
    const parsed = safeParse(raw);
    return { text, vision: String(parsed?.image_text ?? "").includes(code) };
  } catch (error) {
    return { text, vision: false, error: (error as Error).message };
  }
}

function safeParse(raw: string): Record<string, unknown> | null {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

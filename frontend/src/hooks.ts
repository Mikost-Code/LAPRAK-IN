import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useOutletContext } from "react-router-dom";
import { api } from "./api/client";
import type { Lang, Snapshot } from "./api/types";

export const useMe = () => useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
export const useProject = (id: string | undefined) =>
  useQuery({ queryKey: ["project", id], queryFn: () => api.project(id!), enabled: Boolean(id) });
export const useProfiles = () => useQuery({ queryKey: ["profiles"], queryFn: api.profiles });

export interface ProjectCtx {
  project: Snapshot;
  refresh: () => Promise<unknown>;
}

export const useProjectCtx = () => useOutletContext<ProjectCtx>();

export function useRefresh(projectId?: string) {
  const client = useQueryClient();
  return () => Promise.all([
    projectId ? client.invalidateQueries({ queryKey: ["project", projectId] }) : Promise.resolve(),
    projectId ? client.invalidateQueries({ queryKey: ["blockers", projectId] }) : Promise.resolve(),
  ]);
}

export type SaveState = "idle" | "dirty" | "saving" | "saved" | "error";

/** Debounced autosave. `value` is compared by JSON; `save` runs 700 ms after the last change. */
export function useAutosave<T>(value: T, save: (value: T) => Promise<unknown>, deps: unknown[] = []): { state: SaveState; error: string | null; flush: () => Promise<void> } {
  const [state, setState] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const last = useRef(JSON.stringify(value));
  const pending = useRef<T | null>(null);
  const timer = useRef<number | null>(null);
  const saveRef = useRef(save);
  saveRef.current = save;

  const flush = async () => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = null;
    if (pending.current === null) return;
    const next = pending.current;
    pending.current = null;
    setState("saving");
    try {
      await saveRef.current(next);
      last.current = JSON.stringify(next);
      setState("saved");
      setError(null);
    } catch (e) {
      setState("error");
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    const json = JSON.stringify(value);
    if (json === last.current) return;
    pending.current = value;
    setState("dirty");
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(flush, 700);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(value), ...deps]);

  useEffect(() => {
    const handler = () => {
      if (pending.current !== null) void flush();
    };
    window.addEventListener("beforeunload", handler);
    window.addEventListener("pagehide", handler);
    return () => {
      window.removeEventListener("beforeunload", handler);
      window.removeEventListener("pagehide", handler);
      if (pending.current !== null) void flush();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { state, error, flush };
}

export function timeAgo(iso: string, lang: Lang): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(lang === "id" ? "id" : "en", { numeric: "auto" });
  if (diff < 60) return rtf.format(-Math.round(diff), "second");
  if (diff < 3600) return rtf.format(-Math.round(diff / 60), "minute");
  if (diff < 86400) return rtf.format(-Math.round(diff / 3600), "hour");
  return rtf.format(-Math.round(diff / 86400), "day");
}

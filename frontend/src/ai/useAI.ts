import { useCallback, useRef, useState } from "react";
import { api } from "../api/client";
import type { AIProfile, CompleteResult, Snapshot } from "../api/types";
import { useProfiles } from "../hooks";
import { AIRunError, runOperation } from "./runner";

type PrepareBody = Parameters<typeof api.prepare>[1];

/** One AI job at a time per page; the server stores results, the browser does the provider call. */
export function useAI(project: Snapshot | undefined) {
  const profiles = useProfiles();
  const profile: AIProfile | null = profiles.data?.find((p) => p.id === project?.ai_profile_id) ?? null;
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  const run = useCallback(async (body: PrepareBody, label?: string): Promise<CompleteResult | null> => {
    if (!project) return null;
    if (!profile) {
      setError("no_profile");
      return null;
    }
    if (busy) return null;
    controller.current = new AbortController();
    setBusy(label ?? body.operation);
    setError(null);
    try {
      let attempt = 0;
      for (;;) {
        try {
          return await runOperation(project.id, profile, body, { signal: controller.current.signal });
        } catch (e) {
          const err = e as AIRunError;
          attempt += 1;
          if (err instanceof AIRunError && err.retryable && attempt < 3 && !controller.current.signal.aborted) {
            await new Promise((r) => setTimeout(r, 1500 * attempt));
            continue;
          }
          throw e;
        }
      }
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      setBusy(null);
    }
  }, [project, profile, busy]);

  const cancel = useCallback(() => controller.current?.abort(), []);
  return { profile, busy, error, run, cancel, clearError: () => setError(null) };
}

/*
 * The analysis life cycle: submit → poll for progress → finished.
 *
 * Safety measures:
 *  - a "generation" counter discards answers to requests made before the
 *    user moved on (e.g. pressed New analysis while a request was in flight);
 *  - only one poll is in flight at a time, and polling stops on its own once
 *    the job is finished;
 *  - a lost connection is retried with increasing delays instead of failing.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { AnalysisJob } from "../api/types";
import { parseTimestamp } from "../lib/format";

const POLL_INTERVAL_MS = 1000;
const MAX_RETRY_DELAY_MS = 10000;

export type AnalysisState =
  | { phase: "idle" }
  | { phase: "submitting" }
  | { phase: "loading"; jobId: string }
  | { phase: "lost"; jobId: string; message: string }
  | { phase: "tracking"; job: AnalysisJob; connectionError: string | null; cancelling: boolean };

export function isFinished(job: AnalysisJob): boolean {
  return job.status === "completed" || job.status === "failed" || job.status === "cancelled";
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Whichever copy of the job is more recent (protects against out-of-order replies). */
function newer(current: AnalysisJob, incoming: AnalysisJob): AnalysisJob {
  const currentTime = parseTimestamp(current.updated_at) ?? 0;
  const incomingTime = parseTimestamp(incoming.updated_at) ?? 0;
  return incomingTime >= currentTime ? incoming : current;
}

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>({ phase: "idle" });
  const [submitError, setSubmitError] = useState<string | null>(null);
  const generation = useRef(0);
  const stateRef = useRef<AnalysisState>(state);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const submit = useCallback(async (sequence: string, name: string): Promise<string | null> => {
    const ticket = ++generation.current;
    setSubmitError(null);
    setState({ phase: "submitting" });
    try {
      const job = await api.createAnalysis(sequence, name);
      if (ticket !== generation.current) {
        return null;
      }
      setState({ phase: "tracking", job, connectionError: null, cancelling: false });
      return job.id;
    } catch (error) {
      if (ticket === generation.current) {
        setState({ phase: "idle" });
        setSubmitError(describe(error));
      }
      return null;
    }
  }, []);

  const open = useCallback((jobId: string) => {
    const ticket = ++generation.current;
    setSubmitError(null);
    setState({ phase: "loading", jobId });
    api.getAnalysis(jobId).then(
      (job) => {
        if (ticket === generation.current) {
          setState({ phase: "tracking", job, connectionError: null, cancelling: false });
        }
      },
      (error: unknown) => {
        if (ticket === generation.current) {
          setState({ phase: "lost", jobId, message: describe(error) });
        }
      },
    );
  }, []);

  const reset = useCallback(() => {
    generation.current += 1;
    setSubmitError(null);
    setState({ phase: "idle" });
  }, []);

  const cancel = useCallback(() => {
    const current = stateRef.current;
    if (current.phase !== "tracking" || isFinished(current.job) || current.cancelling) {
      return;
    }
    const jobId = current.job.id;
    const ticket = generation.current;
    setState((latest) =>
      latest.phase === "tracking" && latest.job.id === jobId ? { ...latest, cancelling: true } : latest,
    );
    api.cancelAnalysis(jobId).then(
      (job) => {
        if (ticket === generation.current) {
          setState((latest) =>
            latest.phase === "tracking" && latest.job.id === jobId
              ? { ...latest, job: newer(latest.job, job) }
              : latest,
          );
        }
      },
      (error: unknown) => {
        if (ticket === generation.current) {
          const message = describe(error);
          setState((latest) =>
            latest.phase === "tracking" && latest.job.id === jobId
              ? { ...latest, cancelling: false, connectionError: message }
              : latest,
          );
        }
      },
    );
  }, []);

  const clearSubmitError = useCallback(() => setSubmitError(null), []);

  // Poll while a job is being tracked and has not finished.
  const trackedId = state.phase === "tracking" ? state.job.id : null;
  const trackingActive = state.phase === "tracking" && !isFinished(state.job);

  useEffect(() => {
    if (trackedId === null || !trackingActive) {
      return;
    }
    const jobId = trackedId;
    let stopped = false;
    let timer: number | undefined;
    let failures = 0;
    const controller = new AbortController();

    const tick = async () => {
      try {
        const job = await api.getAnalysis(jobId, controller.signal);
        if (stopped) {
          return;
        }
        failures = 0;
        setState((latest) => {
          if (latest.phase !== "tracking" || latest.job.id !== jobId) {
            return latest;
          }
          const merged = newer(latest.job, job);
          return {
            ...latest,
            job: merged,
            connectionError: null,
            cancelling: latest.cancelling && !isFinished(merged),
          };
        });
        if (!isFinished(job)) {
          timer = window.setTimeout(tick, POLL_INTERVAL_MS);
        }
      } catch (error) {
        if (stopped) {
          return;
        }
        const message = describe(error);
        if (error instanceof ApiError && error.status === 404) {
          setState((latest) =>
            latest.phase === "tracking" && latest.job.id === jobId
              ? { phase: "lost", jobId, message }
              : latest,
          );
          return;
        }
        failures += 1;
        setState((latest) =>
          latest.phase === "tracking" && latest.job.id === jobId
            ? { ...latest, connectionError: message }
            : latest,
        );
        timer = window.setTimeout(tick, Math.min(POLL_INTERVAL_MS * 2 ** failures, MAX_RETRY_DELAY_MS));
      }
    };

    timer = window.setTimeout(tick, POLL_INTERVAL_MS);
    return () => {
      stopped = true;
      controller.abort();
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };
  }, [trackedId, trackingActive]);

  return { state, submitError, submit, open, cancel, reset, clearSubmitError };
}

import { useEffect, useState } from "react";
import { api } from "../api/client";

export type BackendStatus =
  | { state: "checking" }
  | { state: "online"; version: string }
  | { state: "offline" };

/**
 * Checks /api/health on load, every `intervalMs`, and whenever the window
 * regains focus. Only one check is ever in flight at a time.
 */
export function useBackendStatus(intervalMs = 15000): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>({ state: "checking" });

  useEffect(() => {
    let stopped = false;
    let timer: number | undefined;
    let inFlight: AbortController | null = null;

    const run = () => {
      if (timer !== undefined) {
        window.clearTimeout(timer);
        timer = undefined;
      }
      inFlight?.abort();
      const controller = new AbortController();
      inFlight = controller;
      const isCurrent = () => !stopped && !controller.signal.aborted;

      api
        .health(controller.signal)
        .then(
          (health) => {
            if (isCurrent()) {
              setStatus({ state: "online", version: health.version });
            }
          },
          () => {
            if (isCurrent()) {
              setStatus({ state: "offline" });
            }
          },
        )
        .finally(() => {
          if (isCurrent()) {
            inFlight = null;
            timer = window.setTimeout(run, intervalMs);
          }
        });
    };

    run();
    window.addEventListener("focus", run);
    return () => {
      stopped = true;
      inFlight?.abort();
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
      window.removeEventListener("focus", run);
    };
  }, [intervalMs]);

  return status;
}

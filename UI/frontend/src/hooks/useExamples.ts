import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ExampleSequence } from "../api/types";

export type ExamplesState =
  | { state: "loading" }
  | { state: "ready"; examples: ExampleSequence[] }
  | { state: "unavailable" };

/** Loads the example proteins; retries automatically when the server comes online. */
export function useExamples(serverOnline: boolean): ExamplesState {
  const [value, setValue] = useState<ExamplesState>({ state: "loading" });

  useEffect(() => {
    if (!serverOnline) {
      return;
    }
    const controller = new AbortController();
    api.examples(controller.signal).then(
      (examples) => setValue({ state: "ready", examples }),
      () => {
        if (!controller.signal.aborted) {
          setValue({ state: "unavailable" });
        }
      },
    );
    return () => controller.abort();
  }, [serverOnline]);

  return value;
}

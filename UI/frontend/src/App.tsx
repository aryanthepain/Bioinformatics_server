/*
 * The app shell: picks which screen to show and keeps the address bar in sync.
 *
 * The current analysis id lives in the URL (?job=...), so refreshing the page
 * or using the browser's back and forward buttons works as expected.
 */
import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import Header from "./components/Header";
import InputScreen from "./components/InputScreen";
import type { Draft } from "./components/InputScreen";
import MessageScreen from "./components/MessageScreen";
import ResultsScreen from "./components/ResultsScreen";
import RunScreen from "./components/RunScreen";
import { useAnalysis } from "./hooks/useAnalysis";
import { useBackendStatus } from "./hooks/useBackendStatus";

const EMPTY_DRAFT: Draft = { sequence: "", name: "" };

function readJobFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get("job");
}

function writeJobToUrl(jobId: string | null): void {
  const url = new URL(window.location.href);
  if (jobId) {
    url.searchParams.set("job", jobId);
  } else {
    url.searchParams.delete("job");
  }
  const next = `${url.pathname}${url.search}${url.hash}`;
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (next !== current) {
    window.history.pushState(null, "", next);
  }
}

export default function App() {
  const backend = useBackendStatus();
  const { state, submitError, submit, open, cancel, reset, clearSubmitError } = useAnalysis();
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);

  // Follow the URL on first load and when the user presses back or forward.
  useEffect(() => {
    const syncWithUrl = () => {
      const jobId = readJobFromUrl();
      if (jobId) {
        open(jobId);
      } else {
        reset();
      }
    };
    syncWithUrl();
    window.addEventListener("popstate", syncWithUrl);
    return () => window.removeEventListener("popstate", syncWithUrl);
  }, [open, reset]);

  const handleSubmit = useCallback(
    (sequence: string, name: string) => {
      void submit(sequence, name).then((jobId) => {
        if (jobId) {
          writeJobToUrl(jobId);
        }
      });
    },
    [submit],
  );

  const startNewAnalysis = useCallback(() => {
    setDraft(EMPTY_DRAFT);
    reset();
    writeJobToUrl(null);
  }, [reset]);

  const editAndRerun = useCallback(
    (sequence: string, name: string) => {
      setDraft({ sequence, name });
      reset();
      writeJobToUrl(null);
    },
    [reset],
  );

  let screen: ReactNode;
  switch (state.phase) {
    case "idle":
    case "submitting":
      screen = (
        <InputScreen
          draft={draft}
          onDraftChange={setDraft}
          onSubmit={handleSubmit}
          submitting={state.phase === "submitting"}
          submitError={submitError}
          onDismissError={clearSubmitError}
          backend={backend}
        />
      );
      break;
    case "loading":
      screen = <MessageScreen title="Loading analysis…" busy />;
      break;
    case "lost": {
      const lostJobId = state.jobId;
      screen = (
        <MessageScreen
          title="This analysis is not available"
          message={state.message}
          actions={[
            { label: "Start a new analysis", onClick: startNewAnalysis, primary: true },
            { label: "Try again", onClick: () => open(lostJobId) },
          ]}
        />
      );
      break;
    }
    case "tracking": {
      const job = state.job;
      screen =
        job.status === "completed" ? (
          <ResultsScreen job={job} onNewAnalysis={startNewAnalysis} />
        ) : (
          <RunScreen
            job={job}
            cancelling={state.cancelling}
            connectionError={state.connectionError}
            onCancel={cancel}
            onNewAnalysis={startNewAnalysis}
            onEditAndRerun={() => editAndRerun(job.query.sequence, job.query.name)}
          />
        );
      break;
    }
  }

  // A failed progress check means the server is unreachable right now, even if
  // the periodic health check has not noticed yet.
  const headerStatus =
    state.phase === "tracking" && state.connectionError !== null ? ({ state: "offline" } as const) : backend;

  return (
    <div className="app">
      <Header backend={headerStatus} onHome={startNewAnalysis} />
      <div className="app__main">{screen}</div>
      <footer className="site-footer">
        <div className="site-footer__inner container">
          Predictions are computational hypotheses and should be confirmed experimentally.
        </div>
      </footer>
    </div>
  );
}

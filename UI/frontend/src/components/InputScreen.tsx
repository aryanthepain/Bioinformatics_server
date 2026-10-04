import { useMemo, useRef, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent, KeyboardEvent } from "react";
import type { ExampleSequence } from "../api/types";
import type { BackendStatus } from "../hooks/useBackendStatus";
import { useExamples } from "../hooks/useExamples";
import { formatCount } from "../lib/format";
import { MAX_SEQUENCE_LENGTH, MIN_SEQUENCE_LENGTH, checkSequence } from "../lib/sequence";
import type { SequenceCheck } from "../lib/sequence";
import "./InputScreen.css";

export interface Draft {
  sequence: string;
  name: string;
}

interface InputScreenProps {
  draft: Draft;
  onDraftChange: (update: (draft: Draft) => Draft) => void;
  onSubmit: (sequence: string, name: string) => void;
  submitting: boolean;
  submitError: string | null;
  onDismissError: () => void;
  backend: BackendStatus;
}

const MAX_FILE_BYTES = 1_000_000;

const LEVEL_GUIDE = [
  {
    title: "Primary structure",
    text: "The amino-acid sequence itself: close homologues, conserved domain families and physicochemical properties.",
  },
  {
    title: "Secondary structure",
    text: "Local folding into helices and strands, predicted per residue and checked against experimentally solved structures.",
  },
  {
    title: "Tertiary structure",
    text: "The three-dimensional fold of the chain. Proteins with similar folds often share a function.",
  },
  {
    title: "Quaternary structure",
    text: "How chains assemble into complexes, and which surfaces form interfaces with partner proteins.",
  },
];

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="7" fill="currentColor" />
      <path d="M5 8.2l2 2 4-4.4" stroke="#ffffff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StatusLine({ check }: { check: SequenceCheck }) {
  switch (check.kind) {
    case "empty":
      return <>Paste a sequence, drop a FASTA file here, or try an example below.</>;
    case "too-short":
      return (
        <>
          {formatCount(check.length)} {check.length === 1 ? "residue" : "residues"} · at least{" "}
          {MIN_SEQUENCE_LENGTH} needed
        </>
      );
    case "invalid":
      return <>{check.message}</>;
    case "valid":
      return (
        <>
          <CheckIcon />
          <span>
            {formatCount(check.sequence.length)} residues
            {check.header ? ` · ${check.header}` : ""} · ready
          </span>
        </>
      );
  }
}

export default function InputScreen({
  draft,
  onDraftChange,
  onSubmit,
  submitting,
  submitError,
  onDismissError,
  backend,
}: InputScreenProps) {
  const examples = useExamples(backend.state === "online");
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const check = useMemo(() => checkSequence(draft.sequence), [draft.sequence]);
  const canSubmit = check.kind === "valid" && !submitting;

  const clearMessages = () => {
    setFileError(null);
    if (submitError) {
      onDismissError();
    }
  };

  const setSequence = (sequence: string) => {
    clearMessages();
    onDraftChange((current) => ({ ...current, sequence }));
  };

  const submit = () => {
    if (canSubmit) {
      onSubmit(draft.sequence, draft.name);
    }
  };

  const handleFormSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      submit();
    }
  };

  const loadFile = async (file: File) => {
    clearMessages();
    if (file.size > MAX_FILE_BYTES) {
      setFileError(`"${file.name}" is too large to be a single protein sequence.`);
      return;
    }
    try {
      const text = await file.text();
      onDraftChange((current) => ({ ...current, sequence: text }));
    } catch {
      setFileError(`Could not read "${file.name}".`);
    }
  };

  const handleFileChosen = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = ""; // allows choosing the same file again
    if (file) {
      void loadFile(file);
    }
  };

  const hasFiles = (event: DragEvent<HTMLDivElement>) =>
    Array.from(event.dataTransfer.types).includes("Files");

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (hasFiles(event)) {
      event.preventDefault();
      setDragging(true);
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) {
      event.preventDefault();
      void loadFile(file);
    }
  };

  const chooseExample = (example: ExampleSequence) => {
    clearMessages();
    onDraftChange(() => ({ sequence: example.sequence, name: example.name }));
  };

  const clearAll = () => {
    clearMessages();
    onDraftChange(() => ({ sequence: "", name: "" }));
  };

  const statusClass =
    check.kind === "valid"
      ? "composer__status composer__status--ok"
      : check.kind === "invalid"
        ? "composer__status composer__status--error"
        : "composer__status";

  return (
    <main className="input-screen container">
      <div className="input-layout">
        <div className="input-main">
          <div className="input-intro">
            <p className="eyebrow">Protein function prediction</p>
            <h1 className="display">From sequence to function</h1>
            <p className="lede">
              Paste an amino-acid sequence. Four structural levels each contribute evidence, and
              are combined into one predicted function.
            </p>
          </div>

          {backend.state === "offline" && (
            <div className="alert alert--error" role="alert">
              <div className="alert__body">
                <span className="alert__title">The analysis server is not responding.</span>
                <span>
                  Start it from <code>UI/backend</code> with{" "}
                  <code>uv run uvicorn app.main:app --reload --port 8000</code>. This page reconnects
                  automatically.
                </span>
              </div>
            </div>
          )}

          <form className="composer" onSubmit={handleFormSubmit} noValidate>
            <div className="composer__head">
              <label className="composer__label" htmlFor="sequence-input">
                Protein sequence
              </label>
              <span className="composer__hint">
                Plain sequence or FASTA · {MIN_SEQUENCE_LENGTH}–{formatCount(MAX_SEQUENCE_LENGTH)} residues
              </span>
            </div>

            <div
              className={`composer__field${dragging ? " composer__field--dragging" : ""}`}
              onDragOver={handleDragOver}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              <textarea
                id="sequence-input"
                className="composer__textarea"
                value={draft.sequence}
                onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setSequence(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={">Query_001\nMSDVAIVKEGWLHKRGEYIKTWRPRYFLLKNDGTFIGYKERPQDVDQREAPLNNFSVAQCQLMKTERPRPNTFIIRCLQ…"}
                rows={8}
                spellCheck={false}
                autoCapitalize="off"
                autoComplete="off"
                disabled={submitting}
                aria-invalid={check.kind === "invalid"}
                aria-describedby="sequence-status"
              />
            </div>

            <p id="sequence-status" className={statusClass} aria-live="polite">
              <StatusLine check={check} />
            </p>

            <div className="composer__footer">
              <div className="name-field">
                <label htmlFor="name-input">Name (optional)</label>
                <input
                  id="name-input"
                  type="text"
                  value={draft.name}
                  maxLength={80}
                  placeholder={check.kind === "valid" && check.header ? check.header : "e.g. Query_001"}
                  onChange={(event: ChangeEvent<HTMLInputElement>) => {
                    const name = event.target.value;
                    onDraftChange((current) => ({ ...current, name }));
                  }}
                  disabled={submitting}
                  autoComplete="off"
                />
              </div>

              <div className="composer__actions">
                <input
                  ref={fileInput}
                  type="file"
                  accept=".fasta,.fa,.faa,.fas,.txt,text/plain"
                  onChange={handleFileChosen}
                  hidden
                />
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={clearAll}
                  disabled={submitting || (draft.sequence === "" && draft.name === "")}
                >
                  Clear
                </button>
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => fileInput.current?.click()}
                  disabled={submitting}
                >
                  Upload FASTA
                </button>
                <button type="submit" className="btn btn--primary" disabled={!canSubmit}>
                  {submitting ? (
                    <>
                      <span className="spinner" aria-hidden="true" />
                      Starting…
                    </>
                  ) : (
                    "Predict function"
                  )}
                </button>
              </div>
            </div>

            {(fileError || submitError) && (
              <div className="composer__error">
                <div className="alert alert--error" role="alert">
                  <div className="alert__body">{fileError ?? submitError}</div>
                  <button
                    type="button"
                    className="alert__close"
                    onClick={clearMessages}
                    aria-label="Dismiss message"
                  >
                    ×
                  </button>
                </div>
              </div>
            )}
          </form>

          <p className="composer__shortcut">
            Tip: press <kbd>⌘</kbd> <kbd>Enter</kbd> (or <kbd>Ctrl</kbd> <kbd>Enter</kbd>) to run.
          </p>

          <div className="examples">
            <span className="examples__label">Try an example</span>
            {examples.state === "ready" &&
              examples.examples.map((example) => (
                <button
                  key={example.key}
                  type="button"
                  className="chip"
                  onClick={() => chooseExample(example)}
                  disabled={submitting}
                  title={`${example.organism} · ${example.reference}`}
                >
                  <span>{example.name}</span>
                  <span className="chip__meta">{example.length} aa</span>
                </button>
              ))}
            {examples.state !== "ready" && (
              <span className="examples__pending">
                {backend.state === "offline" || examples.state === "unavailable"
                  ? "Examples appear once the server is reachable."
                  : "Loading examples…"}
              </span>
            )}
          </div>
        </div>

        <aside className="levels-guide" aria-labelledby="levels-guide-title">
          <h2 id="levels-guide-title" className="levels-guide__title">
            Four levels of evidence
          </h2>
          <ol className="levels-guide__list">
            {LEVEL_GUIDE.map((level, index) => (
              <li key={level.title} className="levels-guide__item">
                <span className="levels-guide__number">{String(index + 1).padStart(2, "0")}</span>
                <span className="levels-guide__name">{level.title}</span>
                <span className="levels-guide__text">{level.text}</span>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </main>
  );
}

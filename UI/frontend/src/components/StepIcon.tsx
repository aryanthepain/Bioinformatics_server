import type { StepStatus } from "../api/types";

const STATUS_LABEL: Record<StepStatus, string> = {
  pending: "Waiting",
  running: "Running",
  completed: "Done",
  failed: "Failed",
  skipped: "Skipped",
  cancelled: "Cancelled",
};

function Icon({ status }: { status: StepStatus }) {
  switch (status) {
    case "pending":
      return (
        <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
          <circle className="step-icon__ring" cx="11" cy="11" r="8.5" strokeWidth="1.8" />
        </svg>
      );
    case "running":
      return (
        <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
          <circle className="step-icon__track" cx="11" cy="11" r="8.5" strokeWidth="2.4" />
          <path className="step-icon__arc" d="M11 2.5a8.5 8.5 0 0 1 8.5 8.5" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
      );
    case "completed":
      return (
        <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
          <circle className="step-icon__fill" cx="11" cy="11" r="10" />
          <path d="M6.8 11.3l2.8 2.8 5.6-6" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "failed":
      return (
        <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
          <circle className="step-icon__fill" cx="11" cy="11" r="10" />
          <path d="M7.8 7.8l6.4 6.4M14.2 7.8l-6.4 6.4" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
        </svg>
      );
    case "skipped":
      return (
        <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
          <circle className="step-icon__ring" cx="11" cy="11" r="8.5" strokeWidth="1.8" strokeDasharray="3 3" />
          <path className="step-icon__mark" d="M7.5 11h7" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );
    case "cancelled":
      return (
        <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
          <circle className="step-icon__ring" cx="11" cy="11" r="8.5" strokeWidth="1.8" />
          <path className="step-icon__mark" d="M7.5 14.5l7-7" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );
  }
}

export default function StepIcon({ status }: { status: StepStatus }) {
  return (
    <span className={`step-icon step-icon--${status}`}>
      <Icon status={status} />
      <span className="visually-hidden">{STATUS_LABEL[status]}</span>
    </span>
  );
}

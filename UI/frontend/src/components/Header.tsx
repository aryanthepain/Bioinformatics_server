import type { BackendStatus } from "../hooks/useBackendStatus";
import "./Header.css";

function LogoMark() {
  return (
    <svg
      width="26"
      height="26"
      viewBox="0 0 28 28"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <rect x="2" y="2" width="24" height="24" rx="6" />
      <path d="M10 6.5c0 3.75 8 3.75 8 7.5s-8 3.75-8 7.5M18 6.5c0 3.75-8 3.75-8 7.5s8 3.75 8 7.5" />
      <path d="M11.2 14h5.6" strokeWidth="1.4" />
    </svg>
  );
}

interface HeaderProps {
  backend: BackendStatus;
  onHome: () => void;
}

const STATUS_LABEL: Record<BackendStatus["state"], string> = {
  checking: "Connecting…",
  online: "Server online",
  offline: "Server offline",
};

export default function Header({ backend, onHome }: HeaderProps) {
  return (
    <header className="site-header">
      <div className="site-header__inner container">
        <button type="button" className="brand" onClick={onHome} title="Start a new analysis">
          <span className="brand__mark">
            <LogoMark />
          </span>
          <span className="brand__name">Protein Function Predictor</span>
        </button>
        <span
          className={`server-status server-status--${backend.state}`}
          title={backend.state === "online" ? `API version ${backend.version}` : undefined}
          role="status"
        >
          <span className="server-status__dot" aria-hidden="true" />
          <span className="server-status__label">{STATUS_LABEL[backend.state]}</span>
        </span>
      </div>
    </header>
  );
}

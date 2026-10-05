interface MessageAction {
  label: string;
  onClick: () => void;
  primary?: boolean;
}

interface MessageScreenProps {
  title: string;
  message?: string;
  busy?: boolean;
  actions?: MessageAction[];
}

export default function MessageScreen({ title, message, busy = false, actions = [] }: MessageScreenProps) {
  return (
    <main className="message-screen container">
      <div className="message-screen__panel" aria-busy={busy}>
        {busy && <span className="spinner message-screen__spinner" aria-hidden="true" />}
        <h1 className="message-screen__title">{title}</h1>
        {message && <p className="message-screen__text">{message}</p>}
        {actions.length > 0 && (
          <div className="message-screen__actions">
            {actions.map((action) => (
              <button
                key={action.label}
                type="button"
                className={`btn ${action.primary ? "btn--primary" : "btn--secondary"}`}
                onClick={action.onClick}
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

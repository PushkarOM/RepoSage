import { useEffect } from "react";
import { CheckCircle, XCircle } from "lucide-react";

const AUTO_DISMISS_MS = 4000;

const KIND_CLASS = {
  success: "text-success border-success/40",
  error: "text-danger border-danger/40",
  info: "text-accent border-accent/40",
};

const KIND_ICON = {
  success: CheckCircle,
  error: XCircle,
};

export function ToastStack({ toasts, onDismiss }) {
  if (toasts.length === 0) return null;
  return (
    <div
      className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"
      role="region"
      aria-label="Notifications"
    >
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} onDismiss={() => onDismiss(t.id)} />
      ))}
    </div>
  );
}

function Toast({ toast, onDismiss }) {
  // Auto-dismiss lives in its own effect so a re-render of the parent
  // stack (new toast added) doesn't reset every existing toast's clock.
  useEffect(() => {
    const id = setTimeout(onDismiss, AUTO_DISMISS_MS);
    return () => clearTimeout(id);
  }, [onDismiss]);

  const Icon = KIND_ICON[toast.kind];

  return (
    <div
      className={`pointer-events-auto flex items-start gap-2 toast-enter bg-elevated border rounded-lg shadow-xl px-5 py-4 max-w-md ${KIND_CLASS[toast.kind] || KIND_CLASS.info}`}
      role={toast.kind === "error" ? "alert" : "status"}
      aria-live={toast.kind === "error" ? "assertive" : "polite"}
    >
      {Icon && <Icon size={18} className="shrink-0 mt-0.5" aria-hidden="true" />}
      <p className="font-mono text-sm text-ink leading-snug flex-1 min-w-0 break-words">
        {toast.message}
      </p>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="font-mono text-base text-muted hover:text-ink cursor-pointer shrink-0 -mr-2 -my-1 px-2 py-1 leading-none"
      >
        ×
      </button>
    </div>
  );
}

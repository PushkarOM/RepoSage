import { createContext, useCallback, useContext, useState } from "react";
import { ToastStack } from "../components/Toast";

const ToastContext = createContext(null);

let nextId = 1;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  // dismiss is wired per-toast (each Toast registers its own setTimeout)
  // so the provider just needs to splice a toast out by id when asked.
  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const pushToast = useCallback(({ kind = "info", message }) => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, kind, message }]);
    return id;
  }, []);

  return (
    <ToastContext.Provider value={{ pushToast, dismiss }}>
      {children}
      <ToastStack toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used inside a ToastProvider");
  }
  return ctx;
}

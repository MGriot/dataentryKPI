import React, { useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { TOAST_EVENT } from '../utils/toast';
import type { ToastMessage as Toast } from '../utils/toast';

export const Toasts: React.FC = () => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const onToast = (e: Event) => {
      const toast = (e as CustomEvent<Toast>).detail;
      setToasts((prev) => [...prev.slice(-3), toast]);
      window.setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== toast.id)), 8000);
    };
    window.addEventListener(TOAST_EVENT, onToast);
    return () => window.removeEventListener(TOAST_EVENT, onToast);
  }, []);

  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className="toast toast-error" role="alert">
          <AlertTriangle size={16} aria-hidden="true" />
          <span style={{ flex: 1 }}>{t.text}</span>
          <button
            type="button"
            className="icon-button"
            aria-label="Dismiss"
            onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>
  );
};

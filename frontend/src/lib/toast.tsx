'use client';

import { createContext, useCallback, useContext, useState } from 'react';

type Toast = { id: number; message: string; tone: 'default' | 'success' | 'danger' };
const ToastContext = createContext<(message: string, tone?: Toast['tone']) => void>(
  () => undefined,
);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((message: string, tone: Toast['tone'] = 'default') => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, message, tone }]);
    setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 3500);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-72 flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={`rounded border px-3 py-2 text-sm shadow-lg backdrop-blur bg-surface-raised/95 ${
              toast.tone === 'success'
                ? 'border-success/50 text-success'
                : toast.tone === 'danger'
                  ? 'border-danger/50 text-danger'
                  : 'border-line text-ink'
            }`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

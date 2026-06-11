"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { CheckCircle2, XCircle, Info } from "lucide-react";

type ToastType = "success" | "error" | "info";
type Toast = { id: number; type: ToastType; msg: string };

const ToastContext = createContext<{ push: (t: ToastType, m: string) => void }>({
  push: () => {},
});

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((type: ToastType, msg: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, type, msg }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);

  // Pakai CSS variables yang sudah ada di globals.css
  // Fallback ke nilai hex supaya tidak blank kalau variabel belum load
  const color: Record<ToastType, string> = {
    success: "var(--green, #4ade80)",
    error:   "var(--pink, #f472b6)",
    info:    "var(--cyan, #67e8f9)",
  };

  const Icon: Record<ToastType, typeof CheckCircle2> = {
    success: CheckCircle2,
    error:   XCircle,
    info:    Info,
  };

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="toast-wrap">
        {toasts.map((t) => {
          const I = Icon[t.type];
          return (
            <div
              key={t.id}
              className="glass fade-up"
              style={{
                padding: "14px 18px",
                display: "flex",
                alignItems: "center",
                gap: 12,
                minWidth: 280,
                maxWidth: 400,
                borderLeft: `3px solid ${color[t.type]}`,
              }}
            >
              <I size={20} color={color[t.type]} style={{ flexShrink: 0 }} />
              <span style={{ fontSize: "0.88rem", color: "var(--text-hi, #f1f5f9)" }}>
                {t.msg}
              </span>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
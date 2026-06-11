"use client";

import { useJob } from "@/components/JobContext";
import { Loader2 } from "lucide-react";

/**
 * JobBanner — muncul di atas konten halaman mana pun saat ada job scraping aktif.
 * Letakkan di dalam <main> di layout.tsx, sebelum {children}.
 */
export function JobBanner() {
  const { activeJob } = useJob();
  if (!activeJob) return null;

  const elapsed = Math.floor((Date.now() - activeJob.startedAt.getTime()) / 1000);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 18px",
        marginBottom: 20,
        borderRadius: 12,
        background: "rgba(99,102,241,0.12)",
        border: "1px solid rgba(99,102,241,0.35)",
        backdropFilter: "blur(8px)",
      }}
    >
      <Loader2
        size={18}
        color="var(--cyan, #67e8f9)"
        style={{ flexShrink: 0, animation: "spin 1s linear infinite" }}
      />
      <div style={{ flex: 1 }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: "var(--text-hi, #fff)" }}>
          Scraping berjalan…
        </span>
        <span style={{ fontSize: 13, color: "var(--text-dim, #94a3b8)", marginLeft: 8 }}>
          {activeJob.label}
        </span>
      </div>
      <span style={{ fontSize: 12, color: "var(--text-dim, #94a3b8)", flexShrink: 0 }}>
        {elapsed}s
      </span>
    </div>
  );
}
"use client";

import { useEffect, useState, useRef } from "react";
import { Bug, RefreshCw, Trash2, Server, Activity, Terminal, Pause, Play } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";

export default function DebugPage() {
  const { push } = useToast();
  const [logs, setLogs] = useState<string[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [system, setSystem] = useState<any>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);

  const loadAll = async () => {
    const [l, h, s] = await Promise.all([api.getLogs(300), api.health(), api.systemInfo()]);
    if (l.success) setLogs(l.data.logs || []);
    if (h.success) setHealth(h.data);
    if (s.success) setSystem(s.data);
  };

  useEffect(() => { loadAll(); }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const t = setInterval(async () => {
      const l = await api.getLogs(300);
      if (l.success) setLogs(l.data.logs || []);
    }, 3000);
    return () => clearInterval(t);
  }, [autoRefresh]);

  useEffect(() => {
    if (autoRefresh && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs, autoRefresh]);

  const clearLogs = async () => {
    const r = await api.clearLogs();
    if (r.success) { push("success", "Logs dibersihkan"); setLogs([]); }
  };

  const logColor = (line: string) => {
    if (line.includes("ERROR") || line.includes("CRITICAL")) return "var(--accent-red)";
    if (line.includes("WARNING")) return "var(--accent-amber)";
    if (line.includes("INFO")) return "var(--accent-green)";
    if (line.includes("DEBUG")) return "var(--text-lo)";
    return "var(--text-mid)";
  };

  return (
    <div className="container-app">
      <header className="fade-up" style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 16 }}>
        <div>
          <h1 style={{ fontSize: "2rem", marginBottom: 6 }}>
            Debug <span className="gradient-text">Panel</span>
          </h1>
          <p style={{ color: "var(--text-lo)", fontSize: "0.95rem" }}>
            Pantau log backend, status sistem, dan diagnosa error secara real-time.
          </p>
        </div>
        <button className="btn btn-glass" onClick={loadAll}><RefreshCw size={16} /> Refresh Semua</button>
      </header>

      {/* Health + System cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginBottom: 22 }}>
        <div className="glass fade-up delay-1" style={{ padding: 22 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <Activity size={20} color="var(--accent-green)" />
            <h3 style={{ fontSize: "1.05rem" }}>Health Status</h3>
          </div>
          {health ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
              <Row label="API" value={health.api} ok={health.api === "running"} />
              <Row label="Session Valid" value={health.session_valid ? "Ya" : "Tidak"} ok={health.session_valid} />
              <Row label="Endpoints File" value={health.endpoints_file_exists ? "Ada" : "Tidak ada"} ok={health.endpoints_file_exists} warn />
              <Row label="Profile Dir" value={health.profile_dir_exists ? "Ada" : "Kosong"} ok={health.profile_dir_exists} warn />
              <Row label="Tracked Profiles" value={String(health.tracked_profiles)} />
              <Row label="Debug Mode" value={health.debug_mode ? "ON" : "OFF"} ok={health.debug_mode} />
            </div>
          ) : <div style={{ color: "var(--accent-red)" }}>Backend offline</div>}
        </div>

        <div className="glass fade-up delay-2" style={{ padding: 22 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <Server size={20} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: "1.05rem" }}>System Info</h3>
          </div>
          {system ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
              <Row label="Python" value={system.python_version?.split(" ")[0]} />
              <Row label="Host" value={`${system.config?.api_host}:${system.config?.api_port}`} />
              <Row label="Headless" value={system.config?.headless ? "Ya" : "Tidak"} />
              <Row label="Rate Gap" value={`${system.config?.min_gap_seconds}s`} />
              <Row label="CWD" value={system.cwd} mono />
            </div>
          ) : <div style={{ color: "var(--text-lo)" }}>Memuat...</div>}
        </div>
      </div>

      {/* Live logs */}
      <div className="glass fade-up delay-3" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 20px",
          borderBottom: "1px solid var(--glass-border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Terminal size={19} color="var(--accent-violet)" />
            <h3 style={{ fontSize: "1.05rem" }}>Live Logs</h3>
            <span className="badge badge-green" style={{ fontSize: "0.7rem" }}>{logs.length} baris</span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-glass" style={{ padding: "8px 14px", fontSize: "0.8rem" }}
              onClick={() => setAutoRefresh(!autoRefresh)}>
              {autoRefresh ? <><Pause size={14} /> Auto</> : <><Play size={14} /> Manual</>}
            </button>
            <button className="btn btn-glass" style={{ padding: "8px 14px", fontSize: "0.8rem" }} onClick={clearLogs}>
              <Trash2 size={14} /> Clear
            </button>
          </div>
        </div>
        <div ref={logRef} style={{
          height: 420, overflowY: "auto", padding: "14px 20px",
          fontFamily: "'SF Mono', Menlo, monospace", fontSize: "0.78rem", lineHeight: 1.7,
          background: "rgba(0,0,0,0.3)",
        }}>
          {logs.length === 0 ? (
            <div style={{ color: "var(--text-lo)", textAlign: "center", paddingTop: 40 }}>
              <Bug size={28} style={{ marginBottom: 10, opacity: 0.5 }} /><br />
              Belum ada log. Lakukan aksi scraping untuk melihat aktivitas.
            </div>
          ) : logs.map((line, i) => (
            <div key={i} style={{ color: logColor(line), whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, ok, warn, mono }: { label: string; value: string; ok?: boolean; warn?: boolean; mono?: boolean }) {
  const color = ok === undefined ? "var(--text-hi)" : ok ? "var(--accent-green)" : warn ? "var(--accent-amber)" : "var(--accent-red)";
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.85rem" }}>
      <span style={{ color: "var(--text-lo)" }}>{label}</span>
      <span style={{ color, fontFamily: mono ? "monospace" : "var(--font-display)", fontWeight: 600,
        fontSize: mono ? "0.72rem" : "0.85rem", maxWidth: "60%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {value}
      </span>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Area, AreaChart,
} from "recharts";
import { TrendingUp, TrendingDown, Trash2, Download, RefreshCw, Plus } from "lucide-react";
import { api, fmtNumber } from "@/lib/api";
import { useToast } from "@/components/Toast";

export default function TrackingPage() {
  const { push } = useToast();
  const [profiles, setProfiles] = useState<any[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [growth, setGrowth] = useState<any>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [showManual, setShowManual] = useState(false);

  const loadProfiles = async () => {
    const r = await api.listProfiles();
    if (r.success) {
      setProfiles(r.data.users || []);
      if (r.data.users?.length && !selected) setSelected(r.data.users[0].username);
    }
    setLoading(false);
  };

  useEffect(() => { loadProfiles(); }, []);

  useEffect(() => {
    if (!selected) return;
    (async () => {
      const r = await api.getGrowth(selected, days);
      setGrowth(r.success ? r.data : null);
      if (!r.success) setGrowth({ error: r.message });
    })();
  }, [selected, days]);

  const handleDelete = async (username: string) => {
    if (!confirm(`Hapus semua data tracking @${username}?`)) return;
    const r = await api.deleteProfile(username);
    if (r.success) {
      push("success", `Data @${username} dihapus`);
      setSelected("");
      loadProfiles();
    } else push("error", r.message);
  };

  const metrics = growth && !growth.error ? [
    { key: "followers", label: "Followers", color: "var(--accent-cyan)" },
    { key: "following", label: "Following", color: "var(--accent-blue)" },
    { key: "tweets", label: "Tweets", color: "var(--accent-violet)" },
    { key: "likes", label: "Likes", color: "var(--accent-pink)" },
  ] : [];

  const chartData = growth?.history?.map((h: any) => ({
    date: h.scraped_at?.slice(5, 10),
    followers: h.followers, following: h.following, tweets: h.tweets, likes: h.likes,
  })) || [];

  return (
    <div className="container-app">
      <header className="fade-up" style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 16 }}>
        <div>
          <h1 style={{ fontSize: "2rem", marginBottom: 6 }}>
            Growth <span className="gradient-text">Tracking</span>
          </h1>
          <p style={{ color: "var(--text-lo)", fontSize: "0.95rem" }}>
            Analisis pertumbuhan followers, following, dan engagement dari waktu ke waktu.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-glass" onClick={() => setShowManual(!showManual)}>
            <Plus size={16} /> Manual Snapshot
          </button>
          <button className="btn btn-glass" onClick={loadProfiles}><RefreshCw size={16} /></button>
        </div>
      </header>

      {showManual && <ManualSnapshot onDone={() => { setShowManual(false); loadProfiles(); }} />}

      {loading ? (
        <div className="glass" style={{ padding: 50, textAlign: "center", color: "var(--text-lo)" }}>Memuat...</div>
      ) : profiles.length === 0 ? (
        <div className="glass fade-up" style={{ padding: 50, textAlign: "center" }}>
          <TrendingUp size={40} color="var(--text-lo)" style={{ marginBottom: 14 }} />
          <p style={{ color: "var(--text-mid)" }}>Belum ada data tracking.</p>
          <p style={{ color: "var(--text-lo)", fontSize: "0.85rem", marginTop: 6 }}>Scrape profil dulu untuk mulai tracking.</p>
        </div>
      ) : (
        <>
          {/* Profile selector */}
          <div className="glass fade-up delay-1" style={{ padding: 16, marginBottom: 20, display: "flex", gap: 10, overflowX: "auto" }}>
            {profiles.map((p) => (
              <button key={p.username} onClick={() => setSelected(p.username)} className="btn"
                style={{
                  background: selected === p.username ? "var(--glass-bg-hover)" : "transparent",
                  border: selected === p.username ? "1px solid var(--accent-cyan)" : "1px solid var(--glass-border)",
                  color: selected === p.username ? "var(--text-hi)" : "var(--text-mid)",
                  whiteSpace: "nowrap", flexShrink: 0,
                }}>
                @{p.username} <span style={{ fontSize: "0.72rem", opacity: 0.6 }}>({p.data_points})</span>
              </button>
            ))}
          </div>

          {growth?.error ? (
            <div className="glass fade-up" style={{ padding: 40, textAlign: "center" }}>
              <p style={{ color: "var(--accent-amber)" }}>{growth.error}</p>
              <p style={{ color: "var(--text-lo)", fontSize: "0.85rem", marginTop: 8 }}>
                Perlu minimal 2 snapshot. Scrape profil ini lagi nanti untuk melihat growth.
              </p>
            </div>
          ) : growth ? (
            <>
              {/* Days filter + actions */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18, flexWrap: "wrap", gap: 12 }}>
                <div style={{ display: "flex", gap: 8 }}>
                  {[7, 30, 90, 365].map((d) => (
                    <button key={d} onClick={() => setDays(d)} className="btn"
                      style={{ padding: "8px 16px", fontSize: "0.82rem",
                        background: days === d ? "var(--glass-bg-hover)" : "transparent",
                        border: days === d ? "1px solid var(--glass-border-hi)" : "1px solid var(--glass-border)",
                        color: days === d ? "var(--text-hi)" : "var(--text-mid)" }}>
                      {d === 365 ? "1 thn" : `${d} hari`}
                    </button>
                  ))}
                </div>
                <div style={{ display: "flex", gap: 10 }}>
                  <a href={api.exportCsvUrl(selected)} className="btn btn-glass" style={{ textDecoration: "none" }}>
                    <Download size={16} /> CSV
                  </a>
                  <button className="btn btn-danger" onClick={() => handleDelete(selected)} style={{ padding: "10px 14px" }}>
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              {/* Metric cards */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 16, marginBottom: 22 }}>
                {metrics.map((m, i) => {
                  const g = growth[m.key];
                  const up = g.growth >= 0;
                  return (
                    <div key={m.key} className={`glass glass-hover fade-up delay-${i + 1}`} style={{ padding: 20 }}>
                      <div style={{ fontSize: "0.82rem", color: "var(--text-lo)", marginBottom: 8 }}>{m.label}</div>
                      <div style={{ fontFamily: "var(--font-display)", fontSize: "1.7rem", fontWeight: 700, color: "var(--text-hi)" }}>
                        {fmtNumber(g.end)}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8,
                        color: up ? "var(--accent-green)" : "var(--accent-red)", fontSize: "0.85rem", fontWeight: 600 }}>
                        {up ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
                        {up ? "+" : ""}{fmtNumber(g.growth)} ({up ? "+" : ""}{g.growth_pct}%)
                      </div>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-lo)", marginTop: 4 }}>
                        {up ? "+" : ""}{g.avg_per_day}/hari
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Chart */}
              <div className="glass fade-up delay-3" style={{ padding: 24, marginBottom: 22 }}>
                <h3 style={{ fontSize: "1.1rem", marginBottom: 18 }}>Tren Followers</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#38e1ff" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="#38e1ff" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="date" stroke="#6b769c" fontSize={12} />
                    <YAxis stroke="#6b769c" fontSize={12} tickFormatter={fmtNumber} />
                    <Tooltip contentStyle={{ background: "rgba(12,16,32,0.95)", border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12, color: "#f4f7ff" }} />
                    <Area type="monotone" dataKey="followers" stroke="#38e1ff" strokeWidth={2.5} fill="url(#grad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="glass fade-up delay-4" style={{ padding: 24 }}>
                <h3 style={{ fontSize: "1.1rem", marginBottom: 18 }}>Following &amp; Tweets</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="date" stroke="#6b769c" fontSize={12} />
                    <YAxis stroke="#6b769c" fontSize={12} tickFormatter={fmtNumber} />
                    <Tooltip contentStyle={{ background: "rgba(12,16,32,0.95)", border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: 12, color: "#f4f7ff" }} />
                    <Line type="monotone" dataKey="following" stroke="#5b8cff" strokeWidth={2.5} dot={false} />
                    <Line type="monotone" dataKey="tweets" stroke="#a577ff" strokeWidth={2.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          ) : (
            <div className="glass" style={{ padding: 40, textAlign: "center", color: "var(--text-lo)" }}>Memuat data...</div>
          )}
        </>
      )}
    </div>
  );
}

function ManualSnapshot({ onDone }: { onDone: () => void }) {
  const { push } = useToast();
  const [form, setForm] = useState({ username: "", followers: 0, following: 0, tweets: 0, likes: 0 });
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!form.username) return push("error", "Username wajib diisi");
    setLoading(true);
    const r = await api.manualTrack(form);
    setLoading(false);
    if (r.success) { push("success", "Snapshot manual ditambahkan"); onDone(); }
    else push("error", r.message);
  };

  const fields = ["followers", "following", "tweets", "likes"] as const;
  return (
    <div className="glass fade-up" style={{ padding: 22, marginBottom: 20 }}>
      <h3 style={{ fontSize: "1.05rem", marginBottom: 16 }}>Tambah Snapshot Manual (backfill)</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1.5fr repeat(4,1fr) auto", gap: 10, alignItems: "end" }}>
        <input className="input" placeholder="username" value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })} />
        {fields.map((f) => (
          <input key={f} className="input" type="number" placeholder={f}
            onChange={(e) => setForm({ ...form, [f]: parseInt(e.target.value) || 0 })} />
        ))}
        <button className="btn btn-primary" onClick={submit} disabled={loading}>
          {loading ? <span className="spinner" /> : "Simpan"}
        </button>
      </div>
    </div>
  );
}

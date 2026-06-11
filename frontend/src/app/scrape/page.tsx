"use client";

import { useState } from "react";
import {
  Search, BadgeCheck, MapPin, Users, UserPlus, MessageSquare, Heart, Lock,
} from "lucide-react";
import { api, fmtNumber } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { useJob } from "@/components/JobContext";

export default function ScrapePage() {
  const { push } = useToast();
  const { isRunning, activeJob, startJob, finishJob } = useJob();

  const [input,   setInput]   = useState("");
  const [loading, setLoading] = useState(false);
  const [result,  setResult]  = useState<any>(null);

  const isBlockedByOther = isRunning && !loading;

  const handleSingle = async () => {
    if (isRunning) { push("error", "Tunggu scraping sebelumnya selesai dulu"); return; }
    if (!input.trim()) return push("error", "Masukkan username atau URL");

    const jobId = startJob("profile", `@${input.trim()} — Profile`);
    setLoading(true); setResult(null);
    try {
      const r = await api.scrapeProfile(input.trim());
      if (r.success) {
        setResult(r.data.data);
        push("success", `Berhasil scrape @${r.data.username} via ${r.data.data.method}`);
      } else {
        push("error", r.message);
      }
    } finally {
      setLoading(false);
      finishJob(jobId);
    }
  };

  return (
    <div className="container-app">
      <header className="fade-up" style={{ marginBottom: 26 }}>
        <h1 style={{ fontSize: "2rem", marginBottom: 6 }}>
          Scrape <span className="gradient-text">Profil</span>
        </h1>
        <p style={{ color: "var(--text-lo)", fontSize: "0.95rem" }}>
          Ambil data profil Twitter/X — GraphQL primary, dengan fallback DOM &amp; HTML meta.
        </p>
      </header>

      {/* Input card */}
      <div style={{ position: "relative" }} className="fade-up delay-1">
        {isBlockedByOther && activeJob && (
          <div style={{
            position: "absolute", inset: 0, borderRadius: 12, zIndex: 10,
            background: "rgba(0,0,0,0.45)", backdropFilter: "blur(3px)",
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 8,
          }}>
            <Lock size={22} color="var(--text-dim, #94a3b8)" />
            <span style={{ fontSize: 13, color: "var(--text-dim, #94a3b8)", textAlign: "center", padding: "0 20px" }}>
              Scraping berjalan: <b style={{ color: "var(--cyan, #67e8f9)" }}>{activeJob.label}</b>
              <br />Tunggu hingga selesai sebelum memulai yang baru.
            </span>
          </div>
        )}

        <div className="glass" style={{ padding: 24, marginBottom: 22 }}>
          <label style={{
            fontSize: "0.85rem", color: "var(--text-mid)", marginBottom: 10,
            display: "block", fontFamily: "var(--font-display)",
          }}>
            Username / @handle / URL
          </label>
          <div style={{ display: "flex", gap: 12 }}>
            <input
              className="input"
              placeholder="elonmusk atau https://x.com/elonmusk"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSingle()}
              disabled={isBlockedByOther}
            />
            <button
              className="btn btn-primary"
              onClick={handleSingle}
              disabled={loading || isBlockedByOther}
              style={{ whiteSpace: "nowrap" }}
            >
              {loading
                ? <span className="spinner" />
                : <><Search size={17} /> {isBlockedByOther ? "Menunggu…" : "Scrape"}</>}
            </button>
          </div>
        </div>
      </div>

      {/* Result */}
      {result && <ProfileCard data={result} />}
    </div>
  );
}

// ── Profile card ──────────────────────────────────────────────────────────────
function ProfileCard({ data }: { data: any }) {
  const stats = [
    { label: "Followers", value: data.followers, icon: Users,         color: "var(--accent-cyan)"   },
    { label: "Following", value: data.following, icon: UserPlus,      color: "var(--accent-blue)"   },
    { label: "Tweets",    value: data.tweets,    icon: MessageSquare, color: "var(--accent-violet)" },
    { label: "Likes",     value: data.likes,     icon: Heart,         color: "var(--accent-pink)"   },
  ];

  return (
    <div className="glass fade-up" style={{ padding: 24, marginBottom: 22 }}>
      <div style={{ display: "flex", gap: 18, alignItems: "center", marginBottom: 20, flexWrap: "wrap" }}>
        {data.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={data.avatar_url}
            alt={data.username}
            width={62} height={62}
            style={{ borderRadius: 16, border: "2px solid var(--glass-border-hi)" }}
            onError={(e: any) => (e.target.style.display = "none")}
          />
        ) : (
          <div style={{
            width: 62, height: 62, borderRadius: 16, background: "var(--glass-bg-hover)",
            display: "grid", placeItems: "center", fontSize: "1.4rem", color: "var(--text-lo)",
          }}>
            {data.username?.[0]?.toUpperCase() || "?"}
          </div>
        )}
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{
              fontFamily: "var(--font-display)", fontSize: "1.2rem",
              fontWeight: 700, color: "var(--text-hi)",
            }}>
              {data.display_name || data.username}
            </span>
            {data.is_verified && <BadgeCheck size={20} color="var(--accent-cyan)" />}
          </div>
          <div style={{ color: "var(--text-lo)", fontSize: "0.9rem" }}>@{data.username}</div>
          {data.location && (
            <div style={{
              display: "flex", alignItems: "center", gap: 5,
              color: "var(--text-lo)", fontSize: "0.82rem", marginTop: 4,
            }}>
              <MapPin size={13} /> {data.location}
            </div>
          )}
        </div>
        <span className="badge badge-green">via {data.method}</span>
      </div>

      {data.bio && (
        <p style={{
          fontSize: "0.9rem", color: "var(--text-mid)", lineHeight: 1.6, marginBottom: 18,
          padding: 14, background: "rgba(0,0,0,0.18)", borderRadius: 12,
        }}>
          {data.bio}
        </p>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
        {stats.map((s) => (
          <div key={s.label} className="glass"
            style={{ padding: "14px 12px", textAlign: "center", background: "rgba(0,0,0,0.2)" }}>
            <s.icon size={18} color={s.color} style={{ marginBottom: 6 }} />
            <div style={{
              fontFamily: "var(--font-display)", fontSize: "1.25rem",
              fontWeight: 700, color: "var(--text-hi)",
            }}>
              {fmtNumber(s.value || 0)}
            </div>
            <div style={{ fontSize: "0.72rem", color: "var(--text-lo)", marginTop: 2 }}>
              {s.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

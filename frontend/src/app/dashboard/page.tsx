"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Users, TrendingUp, Database, Activity, ArrowUpRight, Search, KeyRound,
} from "lucide-react";
import { api, fmtNumber } from "@/lib/api";

export default function Dashboard() {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const [p, h] = await Promise.all([api.listProfiles(), api.health()]);
      if (p.success) setProfiles(p.data.users || []);
      if (h.success) setHealth(h.data);
      setLoading(false);
    })();
  }, []);

  const totalFollowers = profiles.reduce((s, p) => s + (p.current_followers || 0), 0);
  const totalTweets = profiles.reduce((s, p) => s + (p.current_tweets || 0), 0);

  const stats = [
    { label: "Profil Ter-track", value: profiles.length, icon: Users, color: "var(--accent-cyan)" },
    { label: "Total Followers", value: fmtNumber(totalFollowers), icon: TrendingUp, color: "var(--accent-violet)" },
    { label: "Total Tweets", value: fmtNumber(totalTweets), icon: Database, color: "var(--accent-blue)" },
    { label: "Session", value: health?.session_valid ? "Aktif" : "Off", icon: Activity, color: health?.session_valid ? "var(--accent-green)" : "var(--accent-red)" },
  ];

  return (
    <div className="container-app">
      <header className="fade-up" style={{ marginBottom: 30 }}>
        <h1 style={{ fontSize: "2.1rem", marginBottom: 6 }}>
          Selamat datang di <span className="gradient-text">X Scraper</span>
        </h1>
        <p style={{ color: "var(--text-lo)", fontSize: "0.95rem" }}>
          Pantau pertumbuhan profil Twitter/X dengan analitik real-time.
        </p>
      </header>

      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 18, marginBottom: 26 }}>
        {stats.map((s, i) => (
          <div key={s.label} className={`glass glass-hover fade-up delay-${i + 1}`} style={{ padding: 22 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ fontSize: "0.82rem", color: "var(--text-lo)", marginBottom: 10 }}>{s.label}</div>
                <div style={{ fontFamily: "var(--font-display)", fontSize: "1.9rem", fontWeight: 700, color: "var(--text-hi)" }}>
                  {loading ? "…" : s.value}
                </div>
              </div>
              <div style={{ width: 44, height: 44, borderRadius: 12, display: "grid", placeItems: "center",
                background: `${s.color}22`, border: `1px solid ${s.color}44` }}>
                <s.icon size={22} color={s.color} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginBottom: 26 }}>
        <Link href="/scrape" style={{ textDecoration: "none" }}>
          <div className="glass glass-hover fade-up delay-2" style={{ padding: 26, height: "100%" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
                <div style={{ width: 48, height: 48, borderRadius: 13, display: "grid", placeItems: "center",
                  background: "linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))" }}>
                  <Search size={24} color="#fff" />
                </div>
                <div>
                  <h3 style={{ fontSize: "1.1rem" }}>Scrape Profil Baru</h3>
                  <p style={{ fontSize: "0.83rem", color: "var(--text-lo)", marginTop: 2 }}>
                    Ambil data followers, following, tweets
                  </p>
                </div>
              </div>
              <ArrowUpRight size={22} color="var(--text-lo)" />
            </div>
          </div>
        </Link>

        <Link href={health?.session_valid ? "/tracking" : "/login"} style={{ textDecoration: "none" }}>
          <div className="glass glass-hover fade-up delay-3" style={{ padding: 26, height: "100%" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
                <div style={{ width: 48, height: 48, borderRadius: 13, display: "grid", placeItems: "center",
                  background: health?.session_valid
                    ? "linear-gradient(135deg, var(--accent-violet), var(--accent-pink))"
                    : "linear-gradient(135deg, var(--accent-amber), #f59e0b)" }}>
                  {health?.session_valid ? <TrendingUp size={24} color="#fff" /> : <KeyRound size={24} color="#fff" />}
                </div>
                <div>
                  <h3 style={{ fontSize: "1.1rem" }}>{health?.session_valid ? "Lihat Growth" : "Login Dulu"}</h3>
                  <p style={{ fontSize: "0.83rem", color: "var(--text-lo)", marginTop: 2 }}>
                    {health?.session_valid ? "Analisis pertumbuhan profil" : "Setup session untuk mulai"}
                  </p>
                </div>
              </div>
              <ArrowUpRight size={22} color="var(--text-lo)" />
            </div>
          </div>
        </Link>
      </div>

      {/* Tracked profiles preview */}
      <div className="glass fade-up delay-4" style={{ padding: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <h3 style={{ fontSize: "1.15rem" }}>Profil Ter-track Terakhir</h3>
          <Link href="/tracking" style={{ color: "var(--accent-cyan)", fontSize: "0.85rem", textDecoration: "none", fontFamily: "var(--font-display)" }}>
            Lihat semua →
          </Link>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: 30, color: "var(--text-lo)" }}>Memuat...</div>
        ) : profiles.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: "var(--text-lo)" }}>
            Belum ada profil. <Link href="/scrape" style={{ color: "var(--accent-cyan)" }}>Scrape sekarang →</Link>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {profiles.slice(0, 5).map((p) => (
              <div key={p.username} className="glass" style={{ padding: "14px 18px", display: "flex",
                justifyContent: "space-between", alignItems: "center", background: "rgba(0,0,0,0.18)" }}>
                <div style={{ fontFamily: "var(--font-display)", fontWeight: 600, color: "var(--text-hi)" }}>
                  @{p.username}
                </div>
                <div style={{ display: "flex", gap: 24, fontSize: "0.85rem" }}>
                  <span style={{ color: "var(--text-mid)" }}>👥 {fmtNumber(p.current_followers)}</span>
                  <span style={{ color: "var(--text-mid)" }}>🐦 {fmtNumber(p.current_tweets)}</span>
                  <span style={{ color: "var(--text-lo)" }}>{p.data_points} snapshot</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

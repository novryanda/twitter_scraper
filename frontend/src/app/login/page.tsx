"use client";

import { useEffect, useState } from "react";
import {
  KeyRound, Upload, Globe, LogOut, ShieldCheck, ShieldAlert,
  Copy, ChevronDown, ChevronUp, RefreshCw,
} from "lucide-react";
import { api, parseCookies } from "@/lib/api";
import { useToast } from "@/components/Toast";

export default function LoginPage() {
  const { push } = useToast();
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [cookieText, setCookieText] = useState("");
  const [username, setUsername] = useState("");
  const [showGuide, setShowGuide] = useState(true);
  const [polling, setPolling] = useState(false);

  const refresh = async () => {
    const r = await api.authStatus();
    if (r.success) setStatus(r.data);
  };

  useEffect(() => { refresh(); }, []);

  // Poll saat browser login berjalan
  useEffect(() => {
    if (!polling) return;
    const t = setInterval(async () => {
      const r = await api.authStatus();
      if (r.success) {
        setStatus(r.data);
        if (r.data.login_detected || !r.data.is_running) {
          setPolling(false);
          if (r.data.session_valid) push("success", "Login terdeteksi! Session tersimpan.");
        }
      }
    }, 3000);
    return () => clearInterval(t);
  }, [polling, push]);

  const handleImport = async () => {
    const cookies = parseCookies(cookieText);
    if (!cookies) {
      push("error", "JSON tidak valid. Pastikan format dari Cookie-Editor (Export as JSON).");
      return;
    }
    setLoading(true);
    const r = await api.importCookies(cookies, username);
    setLoading(false);
    if (r.success) {
      push("success", `Berhasil import ${r.data.total_cookies} cookies`);
      setCookieText("");
      refresh();
    } else {
      push("error", r.message);
    }
  };

  const handleBrowserLogin = async () => {
    setLoading(true);
    const r = await api.loginBrowser(5, false);
    setLoading(false);
    if (r.success) {
      push("info", "Browser dibuka. Login manual lalu tunggu deteksi otomatis.");
      setPolling(true);
    } else {
      push("error", r.message);
    }
  };

  const handleLogout = async (hard: boolean) => {
    setLoading(true);
    const r = await api.logout(hard);
    setLoading(false);
    if (r.success) { push("success", hard ? "Hard reset berhasil" : "Logout berhasil"); refresh(); }
    else push("error", r.message);
  };

  const valid = status?.session_valid;

  return (
    <div className="container-app">
      <header className="fade-up" style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: "2rem", marginBottom: 6 }}>
          Session <span className="gradient-text">&amp; Login</span>
        </h1>
        <p style={{ color: "var(--text-lo)", fontSize: "0.95rem" }}>
          Autentikasi via Cookie Injector — paste cookies dari Cookie-Editor, atau login lewat browser.
        </p>
      </header>

      {/* Status card */}
      <div className="glass fade-up delay-1" style={{ padding: 24, marginBottom: 22 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{
              width: 56, height: 56, borderRadius: 16, display: "grid", placeItems: "center",
              background: valid ? "rgba(74,222,128,0.15)" : "rgba(251,113,133,0.15)",
              border: `1px solid ${valid ? "rgba(74,222,128,0.35)" : "rgba(251,113,133,0.35)"}`,
            }}>
              {valid ? <ShieldCheck size={28} color="var(--accent-green)" />
                     : <ShieldAlert size={28} color="var(--accent-red)" />}
            </div>
            <div>
              <div style={{ fontFamily: "var(--font-display)", fontSize: "1.15rem", fontWeight: 700, color: "var(--text-hi)" }}>
                {valid ? "Session Valid" : "Belum Ada Session"}
              </div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-lo)", marginTop: 3 }}>
                {valid
                  ? `${status?.session_info?.total_cookies || 0} cookies • @${status?.username || "unknown"}`
                  : "Import cookies atau login via browser untuk mulai"}
              </div>
            </div>
          </div>
          <button className="btn btn-glass" onClick={refresh}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>

        {valid && status?.session_info && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12, marginTop: 20 }}>
            <InfoTile label="auth_token" value={status.session_info.auth_token_preview} />
            <InfoTile label="ct0 (CSRF)" value={status.session_info.ct0_preview} />
            <InfoTile label="Total Cookies" value={String(status.session_info.total_cookies)} />
            <InfoTile label="Preferred" value={status.session_info.has_preferred ? "Lengkap" : "Sebagian"} />
          </div>
        )}

        {valid && (
          <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
            <button className="btn btn-glass" onClick={() => handleLogout(false)} disabled={loading}>
              <LogOut size={16} /> Logout
            </button>
            <button className="btn btn-danger" onClick={() => handleLogout(true)} disabled={loading}>
              Hard Reset
            </button>
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22 }}>
        {/* Cookie import */}
        <div className="glass fade-up delay-2" style={{ padding: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
            <Upload size={20} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: "1.1rem" }}>Import Cookies</h3>
          </div>

          <button
            onClick={() => setShowGuide(!showGuide)}
            className="btn btn-glass"
            style={{ width: "100%", justifyContent: "space-between", marginBottom: 14, fontSize: "0.82rem" }}
          >
            <span>📋 Cara export dari Cookie-Editor</span>
            {showGuide ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>

          {showGuide && (
            <ol style={{ fontSize: "0.82rem", color: "var(--text-mid)", lineHeight: 1.9, paddingLeft: 18, marginBottom: 16 }}>
              <li>Login ke <strong style={{ color: "var(--text-hi)" }}>x.com</strong> di browser</li>
              <li>Install ekstensi <strong style={{ color: "var(--text-hi)" }}>Cookie-Editor</strong></li>
              <li>Klik ikon → <strong style={{ color: "var(--text-hi)" }}>Export</strong> → <strong style={{ color: "var(--text-hi)" }}>Export as JSON</strong></li>
              <li>Paste di bawah ini → klik Import</li>
              <li>Wajib ada: <code style={{ color: "var(--accent-cyan)" }}>auth_token</code> &amp; <code style={{ color: "var(--accent-cyan)" }}>ct0</code></li>
            </ol>
          )}

          <input
            className="input"
            placeholder="Username (opsional)"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={{ marginBottom: 12 }}
          />
          <textarea
            className="textarea"
            placeholder='Paste JSON cookies di sini... [{"name":"auth_token",...}]'
            value={cookieText}
            onChange={(e) => setCookieText(e.target.value)}
            style={{ marginBottom: 14 }}
          />
          <button className="btn btn-primary" style={{ width: "100%" }} onClick={handleImport} disabled={loading || !cookieText}>
            {loading ? <span className="spinner" /> : <><Upload size={16} /> Import Cookies</>}
          </button>
        </div>

        {/* Browser login */}
        <div className="glass fade-up delay-3" style={{ padding: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
            <Globe size={20} color="var(--accent-violet)" />
            <h3 style={{ fontSize: "1.1rem" }}>Login via Browser</h3>
          </div>
          <p style={{ fontSize: "0.86rem", color: "var(--text-mid)", lineHeight: 1.7, marginBottom: 18 }}>
            Alternatif tanpa Cookie-Editor. Backend akan membuka browser Chromium —
            login manual, dan session otomatis tersimpan setelah terdeteksi.
          </p>

          <div className="glass" style={{ padding: 16, marginBottom: 18, background: "rgba(0,0,0,0.2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className={`dot ${polling ? "dot-amber dot-pulse" : status?.is_running ? "dot-amber dot-pulse" : "dot-red"}`}
                    style={polling ? { background: "var(--accent-amber)", boxShadow: "0 0 10px var(--accent-amber)" } : {}} />
              <span style={{ fontSize: "0.85rem", color: "var(--text-mid)" }}>
                {polling || status?.is_running ? "Browser berjalan — menunggu login..." : "Browser idle"}
              </span>
            </div>
            {status?.last_error && (
              <div style={{ fontSize: "0.78rem", color: "var(--accent-red)", marginTop: 8 }}>
                Error: {status.last_error}
              </div>
            )}
          </div>

          <button className="btn btn-primary" style={{ width: "100%",
            background: "linear-gradient(120deg, var(--accent-violet), var(--accent-pink))" }}
            onClick={handleBrowserLogin} disabled={loading || polling}>
            {polling ? <><span className="spinner" /> Menunggu login...</> : <><Globe size={16} /> Buka Browser Login</>}
          </button>

          <div style={{ marginTop: 16, padding: 14, borderRadius: 12, background: "rgba(251,191,36,0.08)",
            border: "1px solid rgba(251,191,36,0.2)", fontSize: "0.78rem", color: "var(--accent-amber)" }}>
            ⚠️ Mode browser butuh display/GUI di mesin backend. Untuk server headless, gunakan Cookie Import.
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass" style={{ padding: "12px 14px", background: "rgba(0,0,0,0.2)" }}>
      <div style={{ fontSize: "0.72rem", color: "var(--text-lo)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </div>
      <div style={{ fontSize: "0.88rem", color: "var(--text-hi)", fontFamily: "monospace", wordBreak: "break-all" }}>
        {value || "—"}
      </div>
    </div>
  );
}

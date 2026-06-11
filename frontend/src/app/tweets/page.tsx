"use client";

import { useState, useEffect, useCallback } from "react";
import {
  MessageCircle, User, Search, MessagesSquare, Heart, Repeat2, Eye,
  BadgeCheck, ExternalLink, Hash, FolderOpen, Download, Trash2,
  RefreshCw, FileJson, CheckCircle2, Clock, Lock,
} from "lucide-react";
import { api, fmtNumber } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { useJob } from "@/components/JobContext";

type Tab = "user" | "replies" | "search" | "exports";

// ── Export file shape ─────────────────────────────────────────────────────────
interface ExportFile {
  filename: string;
  size_bytes: number;
  size_kb: number;
  modified: string;
  mode: string;
  username: string;
  tweets_count: number;
  scraped_at: string;
}

// ── Tweet card ────────────────────────────────────────────────────────────────
function TweetItem({ t }: { t: any }) {
  const cat = t.category as string | undefined;
  const catColor: Record<string, string> = {
    POSITIVE: "var(--green)", NEGATIVE: "var(--pink)", HATE_SPEECH: "var(--red)",
    TOXIC: "var(--amber)", HUMOR: "var(--cyan)", NEUTRAL: "var(--text-dim)",
  };
  return (
    <div className="glass" style={{ padding: 16, marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        {t.user?.profile_image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={t.user.profile_image} alt="" width={36} height={36}
            style={{ borderRadius: "50%" }} />
        )}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
            {t.user?.name || t.user?.username}
            {t.user?.verified && <BadgeCheck size={14} color="var(--cyan)" />}
          </span>
          <span style={{ fontSize: 13, color: "var(--text-dim)" }}>@{t.user?.username}</span>
        </div>
        {cat && (
          <span className="badge" style={{ marginLeft: "auto", color: catColor[cat] || "var(--text-dim)" }}>
            {cat}
          </span>
        )}
      </div>
      <p style={{ margin: "8px 0", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{t.text}</p>
      {t.hashtags?.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "6px 0" }}>
          {t.hashtags.map((h: string, index: number) => (
            // FIX: key sebelumnya hanya `h` — kalau ada hashtag duplikat dalam
            // satu tweet (mis. #MBG muncul dua kali) React error "duplicate key".
            // Solusi: gabungkan nilai hashtag dengan index agar selalu unik.
            <span key={`${h}-${index}`} className="badge" style={{ color: "var(--blue)" }}>
              <Hash size={11} style={{ marginRight: 2 }} />{h}
            </span>
          ))}
        </div>
      )}
      <div style={{ display: "flex", gap: 16, fontSize: 13, color: "var(--text-dim)", marginTop: 8 }}>
        <span title="Likes"><Heart size={13} /> {fmtNumber(t.like_count)}</span>
        <span title="Retweets"><Repeat2 size={13} /> {fmtNumber(t.retweet_count)}</span>
        <span title="Replies"><MessageCircle size={13} /> {fmtNumber(t.reply_count)}</span>
        <span title="Views"><Eye size={13} /> {fmtNumber(t.view_count)}</span>
        {t.url && (
          <a href={t.url} target="_blank" rel="noreferrer"
            style={{ marginLeft: "auto", color: "var(--cyan)", display: "flex", alignItems: "center", gap: 3 }}>
            <ExternalLink size={13} /> Buka
          </a>
        )}
      </div>
    </div>
  );
}

// ── Mode badge ────────────────────────────────────────────────────────────────
const modeBadge: Record<string, { label: string; color: string }> = {
  user_tweets:   { label: "User Tweets", color: "var(--cyan)" },
  tweet_replies: { label: "Replies",     color: "var(--blue)" },
  search:        { label: "Search",      color: "var(--amber)" },
};

// ── Export row ────────────────────────────────────────────────────────────────
function ExportRow({ file, onDelete }: { file: ExportFile; onDelete: (f: string) => void }) {
  const [deleting, setDeleting] = useState(false);
  const mb = modeBadge[file.mode] || { label: file.mode || "—", color: "var(--text-dim)" };

  const handleDelete = async () => {
    if (!confirm(`Hapus file "${file.filename}"?`)) return;
    setDeleting(true);
    await onDelete(file.filename);
    setDeleting(false);
  };

  const fmt = (iso: string) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("id-ID", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    } catch { return iso; }
  };

  return (
    <div className="glass" style={{
      padding: "14px 18px", marginBottom: 10,
      display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap",
    }}>
      <FileJson size={28} color="var(--cyan)" style={{ flexShrink: 0 }} />

      <div style={{ flex: 1, minWidth: 180 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 600, fontSize: 14, wordBreak: "break-all" }}>
            {file.filename}
          </span>
          <span className="badge" style={{ color: mb.color, fontSize: 11, flexShrink: 0 }}>
            {mb.label}
          </span>
        </div>
        <div style={{ display: "flex", gap: 16, marginTop: 5, flexWrap: "wrap", fontSize: 12, color: "var(--text-dim)" }}>
          {file.username && (
            <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <User size={11} />@{file.username}
            </span>
          )}
          {file.tweets_count > 0 && (
            <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <MessageCircle size={11} />{fmtNumber(file.tweets_count)} tweet
            </span>
          )}
          <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <Clock size={11} />{fmt(file.scraped_at || file.modified)}
          </span>
          <span>{file.size_kb} KB</span>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <a href={api.downloadExportUrl(file.filename)} download={file.filename}
          className="btn btn-glass"
          style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, padding: "7px 14px" }}>
          <Download size={14} /> Download
        </a>
        <button onClick={handleDelete} disabled={deleting} className="btn btn-glass"
          style={{ color: "var(--pink)", fontSize: 13, padding: "7px 14px", display: "flex", alignItems: "center", gap: 6 }}>
          {deleting ? <span className="spinner" /> : <Trash2 size={14} />}
          Hapus
        </button>
      </div>
    </div>
  );
}

// ── Exports panel ─────────────────────────────────────────────────────────────
function ExportsPanel() {
  const { push } = useToast();
  const [files, setFiles] = useState<ExportFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await api.listExports();
    setLoading(false);
    if (!r.success) { push("error", r.message || "Gagal memuat daftar exports"); return; }
    setFiles(r.data?.files || []);
    setLastRefresh(new Date());
  }, [push]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (fname: string) => {
    const r = await api.deleteExport(fname);
    if (r.success) {
      push("success", `File "${fname}" dihapus`);
      setFiles((prev) => prev.filter((f) => f.filename !== fname));
    } else {
      push("error", r.message || "Gagal menghapus file");
    }
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontFamily: "Sora, sans-serif", fontSize: 18, margin: 0 }}>File Exports</h2>
          <p style={{ fontSize: 12, color: "var(--text-dim)", margin: "4px 0 0" }}>
            Tersimpan di&nbsp;
            <code style={{ background: "rgba(255,255,255,.07)", padding: "1px 6px", borderRadius: 4 }}>
              backend/exports/
            </code>
            {lastRefresh && <span style={{ marginLeft: 8 }}>· Diperbarui {lastRefresh.toLocaleTimeString("id-ID")}</span>}
          </p>
        </div>
        <button onClick={load} disabled={loading} className="btn btn-glass"
          style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {loading ? <span className="spinner" /> : <RefreshCw size={14} />}
          Refresh
        </button>
      </div>

      <div className="glass" style={{
        padding: "10px 16px", marginBottom: 16,
        display: "flex", alignItems: "center", gap: 10,
        borderLeft: "3px solid var(--cyan)", fontSize: 13,
      }}>
        <CheckCircle2 size={15} color="var(--cyan)" style={{ flexShrink: 0 }} />
        <span style={{ color: "var(--text-dim)" }}>
          File JSON otomatis disimpan setiap kali scrape berhasil. Kamu bisa download atau hapus kapan saja dari sini.
        </span>
      </div>

      {loading && files.length === 0 ? (
        <div className="glass" style={{ padding: 40, textAlign: "center", color: "var(--text-dim)" }}>
          <span className="spinner" style={{ display: "inline-block", marginRight: 8 }} />
          Memuat daftar file...
        </div>
      ) : files.length === 0 ? (
        <div className="glass" style={{ padding: 40, textAlign: "center" }}>
          <FolderOpen size={40} color="var(--text-dim)" style={{ marginBottom: 12, opacity: .5 }} />
          <p style={{ color: "var(--text-dim)", margin: 0 }}>
            Belum ada file export. Lakukan scrape dulu di tab lain.
          </p>
        </div>
      ) : (
        <>
          <div style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 10 }}>
            {files.length} file tersimpan
          </div>
          {files.map((f) => <ExportRow key={f.filename} file={f} onDelete={handleDelete} />)}
        </>
      )}
    </div>
  );
}

// ── Lock overlay — muncul di atas input saat ada job lain berjalan ────────────
function LockOverlay({ job }: { job: { label: string } }) {
  return (
    <div style={{
      position: "absolute", inset: 0, borderRadius: 12, zIndex: 10,
      background: "rgba(0,0,0,0.45)", backdropFilter: "blur(3px)",
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 8,
    }}>
      <Lock size={22} color="var(--text-dim)" />
      <span style={{ fontSize: 13, color: "var(--text-dim)", textAlign: "center", padding: "0 20px" }}>
        Scraping berjalan: <b style={{ color: "var(--cyan)" }}>{job.label}</b>
        <br />Tunggu hingga selesai sebelum memulai yang baru.
      </span>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function TweetsPage() {
  const { push } = useToast();
  const { isRunning, activeJob, startJob, finishJob } = useJob();

  const [tab, setTab] = useState<Tab>("user");
  const [loading, setLoading] = useState(false);

  const [username, setUsername]   = useState("");
  const [tweetUrl, setTweetUrl]   = useState("");
  const [query, setQuery]         = useState("");
  const [maxItems, setMaxItems]   = useState(40);
  const [sortBy, setSortBy]       = useState("newest");
  const [searchType, setSearchType] = useState("Latest");
  const [sentiment, setSentiment] = useState<string | null>(null);

  const [tweets, setTweets]       = useState<any[]>([]);
  const [focal, setFocal]         = useState<any>(null);
  const [summary, setSummary]     = useState<any>(null);
  const [exportFile, setExportFile] = useState<string | null>(null);

  // Job milik halaman ini sendiri
  const [myJobId, setMyJobId] = useState<string | null>(null);
  const isMineRunning = loading; // true hanya kalau JOB-nya dari halaman ini

  // Job dari halaman lain sedang berjalan
  const isBlockedByOther = isRunning && !isMineRunning;

  const reset = () => { setTweets([]); setFocal(null); setSummary(null); setExportFile(null); };

  const run = async () => {
    if (isRunning) { push("error", "Tunggu scraping sebelumnya selesai dulu"); return; }
    reset();

    // Buat label deskriptif untuk banner
    let label = "";
    if (tab === "user")    label = `@${username} — User Tweets`;
    if (tab === "replies") label = `Replies tweet`;
    if (tab === "search")  label = `Search: ${query}`;

    const jobId = startJob(
      tab === "user" ? "user_tweets" : tab === "replies" ? "replies" : "search",
      label,
    );
    setMyJobId(jobId);
    setLoading(true);

    try {
      let r: any;
      if (tab === "user") {
        if (!username.trim()) { push("error", "Masukkan username"); return; }
        r = await api.scrapeUserTweets(username.trim(), maxItems, sentiment);
      } else if (tab === "replies") {
        if (!tweetUrl.trim()) { push("error", "Masukkan URL tweet"); return; }
        r = await api.scrapeReplies(tweetUrl.trim(), maxItems, sortBy, sentiment);
      } else {
        if (!query.trim()) { push("error", "Masukkan query/hashtag"); return; }
        r = await api.scrapeSearch(query.trim(), maxItems, searchType, sentiment);
      }

      if (!r.success) { push("error", r.message); return; }
      const d = r.data;
      if (d._export_file) setExportFile(d._export_file);

      if (tab === "replies") {
        setFocal(d.focal_tweet); setTweets(d.replies || []);
        push("success", `${d.replies_count} replies`);
      } else {
        setTweets(d.tweets || []);
        push("success", `${d.tweets_count} tweet diperoleh`);
      }
      setSummary(d.summary);
    } finally {
      setLoading(false);
      finishJob(jobId);
      setMyJobId(null);
    }
  };

  const tabs: { id: Tab; label: string; icon: any }[] = [
    { id: "user",    label: "Tweet User",      icon: User },
    { id: "replies", label: "Tweet + Replies",  icon: MessagesSquare },
    { id: "search",  label: "Search / Hashtag", icon: Search },
    { id: "exports", label: "File Exports",      icon: FolderOpen },
  ];

  return (
    <div className="container-app fade-up">
      <h1 className="gradient-text" style={{ fontFamily: "Sora, sans-serif", fontSize: 30, marginBottom: 4 }}>
        Tweet / Post Scraper
      </h1>
      <p style={{ color: "var(--text-dim)", marginBottom: 20 }}>
        Ambil tweet milik user, balasan sebuah tweet, atau hasil pencarian. Hasil otomatis tersimpan ke JSON.
      </p>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {tabs.map(({ id, label, icon: Icon }) => (
          <button key={id}
            onClick={() => { setTab(id); if (id !== "exports") reset(); }}
            className={tab === id ? "btn btn-primary" : "btn btn-glass"}>
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {/* Exports tab */}
      {tab === "exports" && <ExportsPanel />}

      {/* Scrape tabs */}
      {tab !== "exports" && (
        <>
          {/* Input card — posisi relative agar overlay bisa absolute di dalamnya */}
          <div style={{ position: "relative" }}>
            {/* Lock overlay kalau ada job dari halaman lain */}
            {isBlockedByOther && activeJob && <LockOverlay job={activeJob} />}

            <div className="glass" style={{ padding: 20, marginBottom: 20 }}>
              {tab === "user" && (
                <input className="input"
                  placeholder="Username, @handle, atau URL profil — mis: https://x.com/gibran_tweet"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={isBlockedByOther} />
              )}
              {tab === "replies" && (
                <input className="input"
                  placeholder="URL tweet (https://x.com/user/status/123...)"
                  value={tweetUrl}
                  onChange={(e) => setTweetUrl(e.target.value)}
                  disabled={isBlockedByOther} />
              )}
              {tab === "search" && (
                <input className="input"
                  placeholder="Kata kunci atau #hashtag"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  disabled={isBlockedByOther} />
              )}

              <div style={{ display: "flex", gap: 12, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
                <label style={{ fontSize: 13, color: "var(--text-dim)" }}>
                  Max&nbsp;
                  <input type="number" min={1} max={300} value={maxItems}
                    onChange={(e) => setMaxItems(Number(e.target.value) || 40)}
                    className="input" style={{ width: 90, display: "inline-block" }}
                    disabled={isBlockedByOther} />
                </label>

                {tab === "replies" && (
                  <label style={{ fontSize: 13, color: "var(--text-dim)" }}>
                    Sort&nbsp;
                    <select className="input" style={{ width: 130, display: "inline-block" }}
                      value={sortBy} onChange={(e) => setSortBy(e.target.value)}
                      disabled={isBlockedByOther}>
                      <option value="newest">Terbaru</option>
                      <option value="oldest">Terlama</option>
                      <option value="likes">Like terbanyak</option>
                    </select>
                  </label>
                )}
                {tab === "search" && (
                  <label style={{ fontSize: 13, color: "var(--text-dim)" }}>
                    Tipe&nbsp;
                    <select className="input" style={{ width: 120, display: "inline-block" }}
                      value={searchType} onChange={(e) => setSearchType(e.target.value)}
                      disabled={isBlockedByOther}>
                      <option value="Latest">Latest</option>
                      <option value="Top">Top</option>
                      <option value="Media">Media</option>
                    </select>
                  </label>
                )}

                <label style={{ fontSize: 13, color: "var(--text-dim)" }}>
                  Sentiment&nbsp;
                  <select className="input" style={{ width: 120, display: "inline-block" }}
                    value={sentiment ?? ""} onChange={(e) => setSentiment(e.target.value || null)}
                    disabled={isBlockedByOther}>
                    <option value="">Off</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="rule">Rule</option>
                    <option value="ml">ML</option>
                  </select>
                </label>

                <button onClick={run}
                  disabled={loading || isBlockedByOther}
                  className="btn btn-primary"
                  style={{ marginLeft: "auto" }}>
                  {loading ? <span className="spinner" /> : <Search size={15} />}
                  {loading ? "Memproses..." : isBlockedByOther ? "Menunggu..." : "Scrape"}
                </button>
              </div>

              <p style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 10 }}>
                Sentiment butuh modul <code>sentiment_analyzer_v2.py</code> di folder backend. Kalau tidak ada, otomatis di-skip.
              </p>
            </div>
          </div>

          {/* Export notice setelah scrape berhasil */}
          {exportFile && (
            <div className="glass" style={{
              padding: "12px 16px", marginBottom: 16,
              display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
              borderLeft: "3px solid var(--green)",
            }}>
              <CheckCircle2 size={16} color="var(--green)" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 13, flex: 1 }}>
                Tersimpan sebagai&nbsp;
                <code style={{ background: "rgba(255,255,255,.07)", padding: "1px 6px", borderRadius: 4 }}>
                  {exportFile}
                </code>
              </span>
              <a href={api.downloadExportUrl(exportFile)} download={exportFile}
                className="btn btn-glass"
                style={{ fontSize: 12, padding: "6px 12px", display: "flex", alignItems: "center", gap: 5 }}>
                <Download size={13} /> Download
              </a>
              <button onClick={() => setTab("exports")} className="btn btn-glass"
                style={{ fontSize: 12, padding: "6px 12px", display: "flex", alignItems: "center", gap: 5 }}>
                <FolderOpen size={13} /> Lihat Semua
              </button>
            </div>
          )}

          {/* Summary */}
          {summary && (
            <div className="glass" style={{ padding: 16, marginBottom: 16, display: "flex", gap: 24, flexWrap: "wrap" }}>
              <div><b>{fmtNumber(summary.total)}</b> item</div>
              {summary.engagement_total && (
                <>
                  <div>❤️ {fmtNumber(summary.engagement_total.likes)}</div>
                  <div>🔁 {fmtNumber(summary.engagement_total.retweets)}</div>
                  <div>👁 {fmtNumber(summary.engagement_total.views)}</div>
                </>
              )}
              {summary.sentiment_breakdown && (
                <div style={{ color: "var(--text-dim)" }}>
                  Sentiment: {Object.entries(summary.sentiment_breakdown).map(([k, v]) => `${k}:${v}`).join("  ")}
                </div>
              )}
            </div>
          )}

          {/* Focal tweet */}
          {focal && focal.tweet_id && (
            <>
              <h3 style={{ marginBottom: 8, color: "var(--text-dim)" }}>Tweet utama</h3>
              <div style={{ borderLeft: "3px solid var(--cyan)", paddingLeft: 10 }}>
                <TweetItem t={focal} />
              </div>
              <h3 style={{ margin: "16px 0 8px", color: "var(--text-dim)" }}>Balasan ({tweets.length})</h3>
            </>
          )}

          {/* Tweets list */}
          {tweets.map((t) => <TweetItem key={t.tweet_id} t={t} />)}

          {!loading && tweets.length === 0 && summary === null && (
            <div className="glass" style={{ padding: 40, textAlign: "center", color: "var(--text-dim)" }}>
              Belum ada data. Pilih mode, isi input, lalu klik Scrape.
            </div>
          )}
        </>
      )}
    </div>
  );
}